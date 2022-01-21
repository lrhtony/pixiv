# -*- coding: utf-8 -*-
import os
import threading
import time

import certifi
import pymongo
import requests
from flask import Flask

app = Flask(__name__)


@app.route('/<image_id>')
def gate(image_id):
    # 各种子函数部分
    cache = {}  # 用于返回多进程的值

    def get_illust_cache(client, pid: int):
        db = client['cache']
        try:
            result = db.illust.find({"pid": pid})[0]
            print(result)
            cache['status'] = True
            cache['pid'] = result['pid']
            cache['images_url'] = result['images_url']
            cache['sanity_level'] = result['sanity_level']
        except IndexError:
            print('无结果')
            cache['status'] = False

    access_token = {}  # 用于多进程返回值

    def get_pixiv_token(client):
        refresh_token = os.getenv("PIXIV_REFRESH_TOKEN")  # 在服务器端使用
        db = client['environment']
        result = db.pixiv.find({"key": "PIXIV_ACCESS_TOKEN"})[0]
        print(result)
        access_token['value'] = result['value']
        access_token['expireIn'] = result['expireIn']
        if access_token['expireIn'] - 500 < time.time():  # 判断过期
            print('access_token已过期')
            response = requests.post(  # 刷新token
                "https://oauth.secure.pixiv.net/auth/token",
                data={
                    "client_id": "MOBrBDS8blbauoSck0ZfDbtuzpyT",
                    "client_secret": "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj",
                    "grant_type": "refresh_token",
                    "include_policy": "true",
                    "refresh_token": refresh_token,
                },
                headers={"User-Agent": "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"},
            )
            data = response.json()
            access_token['value'] = data["access_token"]
            access_token['expireIn'] = round(time.time()) + 3600  # 设置过期时间
            access_token['refresh'] = True
            print(access_token)
        else:
            print('access_token未过期')  # 未过期则直接返回值
            access_token['refresh'] = False
            print(access_token)

    def save_pixiv_token(client, token):
        db = client['environment']
        db.pixiv.update_one({"key": "PIXIV_ACCESS_TOKEN"}, {"$set": {"value": token['value'],
                                                                           "expireIn": token['expireIn']}})

    def save_illust_cache(client, illust_information):
        db = client['cache']
        db.illust.insert_one(illust_information)

    mongo_url = os.getenv("MONGO_URL")
    print(mongo_url)
    main_client = pymongo.MongoClient(mongo_url, tlsCAFile=certifi.where())  # 只构建一个client
    pixiv_path = os.path.splitext(image_id)[0]  # 分割提取pid和序号
    pixiv_path_spilt = pixiv_path.split('-', 1)
    try:
        pixiv_id = int(pixiv_path_spilt[0])
        illust_index = int(pixiv_path_spilt[1])
    except IndexError:
        illust_index = 1  # 如果没有指定索引的话上面就会报错
    except ValueError:
        return "请求格式错误", 404
    print(pixiv_id, illust_index)
    thread_get_illust_cache = threading.Thread(target=get_illust_cache, args=(main_client, pixiv_id,))
    thread_get_pixiv_token = threading.Thread(target=get_pixiv_token, args=(main_client,))
    thread_get_illust_cache.start()  # 多进程同步获取缓存和token
    thread_get_pixiv_token.start()
    thread_get_illust_cache.join()
    if cache['status']:  # 如果存在缓存
        try:
            return cache['images_url'][illust_index - 1]  # 直接处理数据返回
        except IndexError:
            return '超过该id图片数量上限', 404
    thread_get_pixiv_token.join()  # 剩下没有缓存的情况
    if access_token['refresh']:  # 如果刷新了token
        thread_save_pixiv_token = threading.Thread(target=save_pixiv_token, args=(main_client, access_token,))
        thread_save_pixiv_token.start()
    illust = get_illust(access_token['value'], pixiv_id)
    if illust['type'] == 0:
        del illust['type']
        thread_save_illust_cache = threading.Thread(target=save_illust_cache, args=(main_client, illust,))
        thread_save_illust_cache.start()
        try:
            return illust['images_url'][illust_index - 1]
        except IndexError:
            return '超过该id图片数量上限', 404
    elif illust['type'] == 404 or illust['type'] == 500:
        return illust['message'], illust['type']


def get_illust(access_token: str, pid: int):
    illust = {}
    url = 'https://app-api.pixiv.net/v1/illust/detail'
    headers = {
        'host': 'app-api.pixiv.net',
        'app-os': 'ios',
        'app-os-version': '14.6',
        'user-agent': 'PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)',
        'Authorization': 'Bearer %s' % access_token,
        'accept-language': 'zh-cn'
    }
    params = {'illust_id': pid}
    data = requests.get(url=url, headers=headers, params=params).json()
    print(data)
    try:
        illust['pid'] = data['illust']['id']
        page_count = data['illust']['page_count']
        illust['sanity_level'] = data['illust']['sanity_level']
        images_url = []
        if page_count == 1:
            image_url = data['illust']['meta_single_page']['original_image_url']
            images_url.append(image_url)
        else:
            meta_pages = data['illust']['meta_pages']
            for i in meta_pages:
                image_url = i['image_urls']['original']
                images_url.append(image_url)
        illust['images_url'] = images_url
        illust['type'] = 0
        print(illust)
        return illust
    except KeyError:
        user_message = data['error']['user_message']
        sys_message = data['error']['user_message']
        if user_message != '':
            illust['type'] = 404
            illust['message'] = user_message
        elif sys_message != '':
            illust['type'] = 500
            illust['message'] = sys_message
        return illust


if __name__ == '__main__':
    app.run(debug=True)


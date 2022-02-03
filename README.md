# pixiv
pixiv图片代理，参考<https://pixiv.cat>

## 使用
在链接后输入pid，如
```
https://pixiv.shojo.cn/34844544
```
或在pid后指定序号，如
```
https://pixiv.shojo.cn/34844544-1
```

## 工作原理
用户发出请求后，查询MongoDB是否有缓存，有缓存则直接返回相关数据

若无缓存，则会尝试从MongoDB中获取pixiv的access_token。若access_token已过期，则会通过环境变量中的refresh_token请求pixiv的api刷新access_token，并将其存入MongoDB中。

最后使用access_token，请求pixiv的api获取图片数据，存入MongoDB中的的缓存并返回给用户

## 部署方法
1. 准备好MongoDB
    1. 到[MongoDB官网](https://www.mongodb.com/)获取一个免费的MongoDB数据库。由于使用的是Vercel免费的Serverless服务，因此尽量选择在美国AWS的数据库。
    2. 在数据库中分别创建在`cache`database下的`illust`collection和在`environment`database下的`pixiv`collection
    3. 在`pixiv`下创建`PIXIV_ACCESS_TOKEN`，如图所示![HEOgEt.md.jpg](https://s4.ax1x.com/2022/02/03/HEOgEt.md.jpg)
    4. 记住该数据库的地址，暂时不支持`mongo+srv://`格式的uri
2. 准备好pixiv的`refresh_token`
    - 使用[该脚本](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362)获取`refresh_token`
3. 搭建图片反向代理
    - 有能力者可以自建反向代理服务器，反向代理`i.pximg.net`
    - 若无法自建反向代理服务器，可以使用Cloudflare的服务
        - 若有顶级域名，可将域名通过NS/CDN方式接入Cloudflare，记录类型选择`CNAME`，名称根据你的需要填入，内容填入`i.pximg.net`，并开启代理。然后在`规则->转换规则`处，创建`修改请求头`规则，如下图设置![7vdVLq.jpg](https://s4.ax1x.com/2022/01/28/7vdVLq.jpg)
        - 若无顶级域名，则使用Cloudflare Workers搭建反向代理，每日100,000次请求，参考代码来自[pixiv.cat](https://pixiv.re/reverseproxy.html)
            ```
            addEventListener("fetch", event => {
            let url = new URL(event.request.url);
            url.hostname = "i.pximg.net";

            let request = new Request(url, event.request);
            event.respondWith(
                fetch(request, {
                headers: {
                    'Referer': 'https://www.pixiv.net/',
                    'User-Agent': 'Cloudflare Workers'
                }
                })
              );
            });
            ```
4. 部署到[Vercel](https://vercel.com)
    1. 点击按钮[![Vercel](https://vercel.com/button)](https://vercel.com/import/project?template=https://github.com/lrhtony/pixiv)
    2. 在部署时配置环境变量`MONGO_URI`为步骤1的MongoDB地址，
    `PIXIV_REFRESH_TOKEN`为步骤2获取的`refresh_token`，`PROXY_HOST`为步骤3配置的反向代理服务器host，注意不要有`http/https`的协议头

## 感谢
[upbit/pixivpy](https://github.com/upbit/pixivpy)

[ZipFile](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362)

[alisaifee/flask-limiter](https://github.com/alisaifee/flask-limiter)
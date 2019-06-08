# dmoj_problems
这是一个[dmoj](https://dmoj.ca)的爬虫程序，获取dmoj的题目信息，保存为dmoj的数据库格式，可以导入到使用dmoj搭建的oj系统。题目信息包括题目类型、题目分组和题目描述。题目的测试数据是无法爬取的，要真正可用还需要自己建立测试数据。



# 爬虫解决的问题

爬虫主要解决了html到markdown的转换以及题目描述中的LaTeX公式和svg提取。dmoj中题目的描述使用markdown语法，因此爬取的html需要转为markdown。

1. markdown转换

   html转markdown的方案中，有html2text和pypandoc两种可选。pypandoc更强大，支持各种文档类型之间的转换，但是dmoj中的嵌入式公式采用\~包围，并非标准的\$包围，采用pypandoc转换后使用的标准的\$。html2text并不支持公式，但是扩展相对简单。因此最后采用html2text进行转换。

2. LaTeX公式和svg提取

   目前只对dmoj题目描述中的公式和svg进行markdown转换处理。方法是对html2text进行扩展，定义自己的tag处理函数。
   
   * LaTeX公式
   
     requests-html会进行js渲染，如果进行了js渲染，那么返回的html变成了math标签，这时公式字符串在annotation标签中，其他m*标签数据需要忽略，然后加上\~包围；如果没有进行js渲染，那么返回的html直接是公式字符串（其中已经包含\~），由html2text提取即可，此时只需要过滤掉服务端生成的公式svg，这个svg是为了客户端不支持公式渲染时使用的。
   
   * svg
   
     html2text没有处理svg，只是把其中的数据提取出来。对于svg，在转换为markdown后，需要保留svg的完整html，这样才能用svg显示。
   
   

# 使用方法

1. 需要python3，因为requests-html只支持python3.6

2. 安装依赖的包： `pip install -r requirements.txt`

3. 执行`python dmoj.py`，生成problemtypes.json，problemgroups.json和problems.josn

4. 将上述problem*.json拷贝到dmoj站点的judge/fixtures目录下

5. 加载数据到数据库，在dmoj站点根目录下执行：

   ```shell
   python manage.py loaddata problemtypes
   python manage.py loaddata problemgroups
   python manage.py loaddata problems
   ```
   
   

# 使用注意

1. 爬取并发任务数

   在中国，dmoj的一些js采用了百度CDN，百度CDN进行了并发限制，一旦检测到并发过多，就会需要输入验证码才能访问，因此并发数必须设为1，默认的并发数也是1；

2. allowed_languages

   生成的problems.json中的allowed_languages字段在代码中是写死了，需要根据情况修改。安装dmoj时采用`python manage.py loaddata language_small`初始化，language只有1到8，此时allowed_languages填写为`[1,2,3,4,5,6,7,8]`，我又增加了V8JS语言，因此代码中我填为`[1,2,3,4,5,6,7,8,9]`；

3. 时间字段

   生成的problems.json中date字段填为一个带时区的时间，如果django的USE_TZ设为False，在执行`python manage.py loaddata`时就会报如下错误，需要将problems.json中的时间修改为不带时区的时间。

   > MySQL backend does not support timezone-aware datetimes when USE_TZ is False
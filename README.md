# python-webapp
*根据[廖雪峰老师教程](https://www.liaoxuefeng.com/wiki/1016959663602400/1018138095494592)所做练习*

分支名|内容
---|---
Day-01|搭建开发环境
Day-02|编写Web App骨架
Day-03|编写ORM

### Day 1 搭建开发环境
#### 项目结构

    awsome-python3-webapp/  <- 根目录
    +- backup/              <- 备份目录
    +- conf/                <- 配置文件
    +- dist/                <- 打包目录
    +- www/                 <- web目录，存放.py文件
    |   +- static/          <- 存放静态文件
    |   +- templates/       <- 存放模板文件
    +- ios/                 <- 存放iOS App工程
    +- LICENSE              <- 代码LISENSE

### Day 2 编写Web APP骨架
使用`aiohttp`，廖雪峰教程已过时，参考[最新版参考文档](https://docs.aiohttp.org/en/latest/)

### Day 3 编写ORM
一旦使用异步，则系统每一层都必须是异步，使用`aiomysql`
> “开弓没有回头箭”

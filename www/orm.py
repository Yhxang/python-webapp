#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
# 考虑实现一个User对象，然后把数据库表users和它关联起来：

class User(Model):
    __table__ = 'users'

    id = IntegerField(primary_key=True)
    name = StringField()

# 定义在User类中的__table__、id和name是类属性。类级别上定义的属性用来描述User对象和表的映射关系，
# 而实例属性必须通过__init__方法初始化，两者互不干扰：

# 创建实例：
user = User(id=123, name='yhxang')

# 存入数据库：
user.insert()

# 查询所有的User对象：
users = User.findAll()

'''

import asyncio
import logging
import aiomysql


def log(sql, args=()):
    logging.info('SQL: %s' % sql)

# 创建连接池
# 创建全局连接池，每个HTTP请求都可以从连接池中直接获取数据库连接。
# 使用连接池好处：不必频繁的打开和关闭数据库连接，而是能复用就复用：

async def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool  # 连接池由全局变量__pool存储，缺省下将编码设置为utf8，自动提交事务
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )

# Select 要执行SELECT语句，我们用select函数执行，需要传入SQL语句和SQL参数：

async def select(sql, args, size=None):
    log(sql, args)
    global __pool
    async with __pool.get() as conn:
        # 设置 DictCursor 后，select查询结果由tuple变为dict模式： 
        # [(1, 'yhxang'), (2, 'Jim')]
        # ====>
        # [ {'id':1, 'name':'yhxang'}, {'id':2, 'name':'Jim'} ]
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # SQL语句的占位符是?，而MySQL的占位符是%s，select()函数在内部自动替换。
            # 注意要始终坚持使用带参数的SQL，而不是自己拼接SQL字符串，这样可以防止SQL注入攻击。
            # await(/yield from)将调用一个子协程（也就是在一个协程中调用另一个协程）并直接获得子协程的返回结果。
            await cur.execute(sql.replace('?', '%s'), args or ())

            if size:
                # 如果传入size参数，就通过fetchmany()获取最多指定数量的记录
                rs = await cur.fetchmany(size)
            else:
                # 否则，通过fetchall()获取所有记录。
                rs = await cur.fetchall()
        logging.info('row returned: %s' % len(rs))
        return rs

# 要执行INSERT、UPDATE、DELETE语句，可以定义一个通用的execute()函数，
# 因为这3种SQL的执行都需要相同的参数，以及返回一个整数表示影响的行数
# execute()函数和select()函数所不同的是，cursor对象不返回结果集，而是通过rowcount返回结果数。
async def execute(sql, args, autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit: 
                # 如果autocommit(自动提交)为True就不用了管是否提交以及提交失败了，
                # autocommit为False,就需要自己提交，提交出现错误，也要回滚（rollback）
                await conn.commit()
        except BaseException as e:
            if not autocommit: 
                await conn.rollback()
            raise
        return affected

# 处理 execute(sql,args) 中的args参数，用','拼接数量为num的'?'，后期会换成%s，由 '?,?,...' 变为 '%s,%s,...'
def create_args_string(num):
    L = []
    for _ in range(num):
        L.append('?')
    return ', '.join(L)

class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):

    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)
    
class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        # 排除Model类本身:
        if name=='Model':
            return type.__new__(cls, name, bases, attrs)
        # 获取table名称:
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        # 获取所有的Field和主键名:
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    # 找到主键:
                    if primaryKey: # 一条数据若有第二个主键，则抛出错误
                        raise Exception('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey: # 如果一条数据中没有主键，抛出错误
            raise Exception('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k) # 从类属性中删除该Field属性，否则，容易造成运行时错误（实例的属性会遮盖类的同名属性）
        escaped_fields = list(map(lambda f: '`%s`' % f, fields)) # 字段加入反引号，防止与SQL关键字冲突
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系 --> {'id'：<IntegerField object>,'name':<StringField object>, ...}
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey # 主键属性名 -->'id'
        attrs['__fields__'] = fields # 除主键外的属性名 --> ['name',...]
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName) # 为何第一个总是主键？？
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        # (mappings.get(f).name or f) 查找User内Field的name值，如果有就取，没有就直接用User类属性名，举例：
        # class User(Model):
        #   id = IntegeField(primary_key=True)
        #   name = StringField()
        #   email = StringField('email')
        # 这时email能用mapping.get(f).name获取到，id和name 则获取不到，只能取类属性名，也就是fields键名
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):

    def __init__(self, **kw):
        super(Model, self).__init__(**kw) # User(id=123, name='yhxang') ==> dict(**kw) ==> {id:123, name:yhxang}

    # 父类是dict，所以可以 user[id]，实现__getattr__()和__setattr__()后，可以实现 user.id
    def __getattr__(self, key): 
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key): #为何不直接使用getattr，难道就为增加个缺省None？
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None: # 处理field.default可以是函数的情况
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value
    
    # 根据WHERE条件查找
    # 假设 --> User.findAll(where='w=2',orderBy='id ASC')
    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        ''' 
        find objects by where clause.
        关键词参数 kw 可以接受 orderBy 和 limit (int或tuple)
        '''
        sql = [cls.__select__] # sql --> ['select `id`, `name` from `users`']
        if where:
            sql.append('where') # sql --> ['select `id`, `name` from `users`', 'where']
            sql.append(where) # sql --> ['select `id`, `name` from `users`', 'where', 'w=2']
        if args is None:
            args = [] # 默认参数必须指向不变对象，不可以： func(args=[])
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by') # sql --> ['select `id`, `name` from `users`', 'where', 'w=2', 'order by']
            sql.append(orderBy) # sql --> ['select `id`, `name` from `users`', 'where', 'w=2', 'order by', 'id ASC']
        limit = kw.get('limit', None) 
        # limit可以一个参数也可以两个参数：limit 5 相当于 limit 0,5 
        # 接受一个int参数，如：func(limit=5) 或一个tuple参数，如： func(limit=(10,15))
        if limit is not None:
            sql.append('limit')
            # sql --> ['select `id`, `name` from `users`', 'where', 'w=2', 'order by', 'id ASC', 'limit']
            if isinstance(limit, int):
                # 假设--> User.findAll(where='w=2', orderBy='id ASC', limit=5)
                sql.append('?')
                # sql --> ['select `id`, `name` from `users`', 'where', 'w=2', 'order by', 'id ASC', 'limit', '?']
                args.append(limit)
                # args --> [5]
            elif isinstance(limit, tuple) and len(limit) == 2: 
                # 假设--> User.findAll(where='w=2', orderBy='id ASC', limit=(10,15))
                sql.append('?, ?')
                # sql --> ['select `id`, `name` from `users`', 'where', 'w=2', 'order by', 'id ASC', 'limit', '?,?' ]
                args.extend(limit)
                # args --> [10, 15]
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args) 
        # 拼接后：--> await select('select `id`, `name` from `users` where w=2 order by id ASC limit ?,?', [10, 15])
        # rs 举例 -->  [ {'id':1, 'name':'yhxang'}, {'id':2, 'name':'Jim'} ]
        return [cls(**r) for r in rs] 
        # 通过关键词参数实例化cls，cls在假设举例中为User
        # --> [User(id=1, name='yhxang'), User(id=2, name='Jim')] 
        # --> [<User ojbect>, <User object>, ...]

    # 根据WHERE条件查找，但返回的是整数，适用于 select count(*) 类型的SQL
    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        # ？？？？？？？？？？？存疑？？？？？？？？？？存疑？？？？？？？？？存疑？？？？？？？？？？？？？
        # --> [{_num_: 5}] 返回selectField不为Null的行数，并用_num_表示，等于select count(selectField) as _num_ from...
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        ' find object by primary key. '
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        # --> [{'id':1, 'name': 'yhxang'}]
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    # user = await User.find('123')

    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__)) # 取得主键外field的值，User参数未设置的话，取default
        args.append(self.getValueOrDefault(self.__primary_key__)) # 取得主键值，User参数未设置的话，取default
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)
    # save使用方法：
    # user = User(id=123, name='yhxang')
    # await user.save()

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args) 
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)
    # update使用方法：
    # user= User(id=1, name='yhxang_1111')
    # await user.update()

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)
   
    # remove使用方法：
    # user= User(id=1)
    # await user.remove()
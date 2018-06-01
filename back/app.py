from tornado.web import RequestHandler, Application, HTTPError, _time_independent_equals
from tornado.ioloop import IOLoop
from tornado.websocket import WebSocketHandler
import tornado.escape
from tornado import gen
from tornado_cors import CorsMixin
import tornadis
import json
import hashlib
from datetime import datetime
import base64

r = tornadis.Client(host="redis", port=6379, autoconnect=True, db=2)
FRONT_DOMAIN = '127.0.0.1:3000'


def b_utf(string):
    return string.decode('utf-8')


def get_chatname(user1, user2):
    if user1 < user2:
        return '{}_{}'.format(user1, user2)
    return '{}_{}'.format(user2, user1)


def authenticated_async(method):
    @gen.coroutine
    def wrapper(self, *args, **kwargs):
        self._auto_finish = False
        username = yield self.current_user
        if not username:
            raise HTTPError(403, "Not authorized")
        else:
            result = method(self, *args, **kwargs)
            if result is not None:
                yield result

    return wrapper


class BaseHandler(RequestHandler):
    def check_xsrf_cookie(self):
        print(self.xsrf_token)
        token = json.loads(self.request.body).get('_xsrf')
        if not token:
            raise HTTPError(403, "'_xsrf' argument missing from POST")
        token = self.get_secure_cookie('_xsrf', token)
        _, token, _ = self._decode_xsrf_token(b_utf(token))
        _, expected_token, _ = self._get_raw_xsrf_token()
        if not token:
            raise HTTPError(403, "'_xsrf' argument has invalid format")
        if not _time_independent_equals(token, expected_token):
            raise HTTPError(403, "XSRF cookie does not match POST argument")

    @gen.coroutine
    def get_current_user(self):
        username = self.request.arguments.get('user')
        if username:
            username = b_utf(self.get_secure_cookie('user', username[0]))

            db_resp = yield r.call('smembers', 'registered')
            users = [b_utf(user) for user in db_resp]
            if not username in users:
                return None
            return username
        else:
            return None


class RegistrationHandler(CorsMixin, BaseHandler):
    CORS_ORIGIN = '*'
    CORS_HEADERS = 'Content-Type'
    CORS_METHODS = 'GET, POST'
    CORS_CREDENTIALS = True
    CORS_EXPOSE_HEADERS = 'Location, X-WP-TotalPages'

    @gen.coroutine
    def post(self):
        data = json.loads(self.request.body)
        exists = yield r.call('sismember', 'registered', data.get('login'))
        if exists:
            self.write(json.dumps({'result': 'ERR', 'description': 'username already exists'}))
        else:
            pipe = tornadis.Pipeline()
            pipe.stack_call('sadd', 'registered', data.get('login'))
            pipe.stack_call('set', 'user:{}'.format(data.get('login')), data.get('password'))
            pipe.stack_call('publish', 'registered', data.get('login'))
            yield r.call(pipe)

            self.write(json.dumps({'result': 'OK'}))
        self.set_status(200)


class LoginHandler(CorsMixin, BaseHandler):
    CORS_ORIGIN = '*'
    CORS_HEADERS = 'Content-Type'
    CORS_METHODS = 'GET, POST'
    CORS_CREDENTIALS = True
    CORS_EXPOSE_HEADERS = 'Location, X-WP-TotalPages'

    @gen.coroutine
    def post(self):
        data = json.loads(self.request.body)
        exists = yield r.call('sismember', 'registered', data.get('login'))
        if exists:
            password = yield r.call('get', 'user:{}'.format(data.get('login')))
            if b_utf(password) == data.get('password'):
                self.write(json.dumps({
                    'result': 'OK',
                    'c': {
                        'user': b_utf(self.create_signed_value('user', data.get('login'))),
                    }
                }))
            else:
                self.write(json.dumps({'result': 'ERR', 'description': 'wrong password'}))
        else:
            self.write(json.dumps({'result': 'ERR', 'description': 'username not exists'}))
        self.set_status(200)


class MainHandler(CorsMixin, BaseHandler):
    CORS_ORIGIN = '*'
    CORS_HEADERS = '*'
    CORS_METHODS = 'GET, POST'
    CORS_CREDENTIALS = True
    CORS_EXPOSE_HEADERS = '*'

    @gen.coroutine
    def get(self):
        username = yield self.current_user
        if username:
            db_resp = yield r.call('smembers', 'registered')
            users = [b_utf(user) for user in db_resp]
            users.remove(username)
            chats = {}
            for chat in users:
                texts = yield r.call('lrange', 'texts:{}'.format(get_chatname(username, chat)), 0, -1)
                senders = yield r.call('lrange', 'senders:{}'.format(get_chatname(username, chat)), 0, -1)
                times = yield r.call('lrange', 'times:{}'.format(get_chatname(username, chat)), 0, -1)
                chats[chat] = {
                    'messages': [{
                        'text': b_utf(texts[i]),
                        'sender': b_utf(senders[i]),
                        'time': b_utf(times[i])
                    } for i in range(len(texts))],
                    'online': False
                }
            db_resp = yield r.call('smembers', 'online')
            online = [b_utf(user) for user in db_resp]
            try:
                online.remove(username)
            except:
                pass

            for chat in online:
                chats[chat]['online'] = True
            self.write(json.dumps({
                'result': 'OK',
                'auth': True,
                'c': {},
                'chats': chats,
                'username': username
            }))
        else:
            self.write(json.dumps({
                'result': 'OK',
                'auth': False,
                'c': {}
            }))

        self.set_status(200)


class ChatSocketHandler(WebSocketHandler):
    waiters = set()

    @gen.coroutine
    def get_current_user(self):
        username = self.request.arguments.get('user')
        if username:
            try:
                username = self.get_secure_cookie('user', username[0]).decode('utf-8')
            except:
                return None
            db_resp = yield r.call('smembers', 'registered')
            users = [b_utf(user) for user in db_resp]
            if not username in users:
                return None
            return username
        else:
            return None

    def check_origin(self, origin):
        return True

    @staticmethod
    def get_date_str():
        return '{0:%H:%M:%S %d/%m/%Y}'.format(datetime.now())

    @authenticated_async
    @gen.coroutine
    def open(self):
        username = yield self.current_user
        for waiter in self.waiters:
            waiter[1].write_message(json.dumps({
                'act': 'sonline',
                'user': username
            }))
        yield r.call('sadd', 'online', username)
        self.waiters.add((username, self))
        self.listen()

    @authenticated_async
    @gen.coroutine
    def on_close(self):
        username = yield self.current_user
        yield r.call('srem', 'online', username)
        self.waiters.remove((username, self))
        for waiter in self.waiters:
            waiter[1].write_message(json.dumps({
                'act': 'soffline',
                'user': username
            }))

    @authenticated_async
    @gen.coroutine
    def on_message(self, message):
        username = yield self.current_user
        message = json.loads(message)
        if message.get('act') == 'message':
            date = self.get_date_str()
            chatname = get_chatname(username, message.get('to'))

            pipe = tornadis.Pipeline()
            pipe.stack_call('rpush', 'texts:{}'.format(chatname), message.get('text'))
            pipe.stack_call('rpush', 'senders:{}'.format(chatname), username)
            pipe.stack_call('rpush', 'times:{}'.format(chatname), date)
            q = yield r.call(pipe)

            for waiter in self.waiters:
                if waiter[0] == message.get('to'):
                    waiter[1].write_message(json.dumps({
                        'act': 'imessage',
                        'from': username,
                        'time': date,
                        'text': message.get('text')
                    }))
            self.write_message(
                json.dumps({'act': 'rmessage', 'id': message.get('id'), 'time': date, 'receiver': message.get('to')}))

    @authenticated_async
    @gen.coroutine
    def listen(self):
        self.client = tornadis.PubSubClient(host="redis", port=6379, autoconnect=True, db=2)
        q = yield self.client.pubsub_subscribe("registered")
        while True:
            msg = yield self.client.pubsub_pop_message()
            username = b_utf(msg[2])
            for waiter in self.waiters:
                waiter[1].write_message(json.dumps({
                    'act': 'iregistered',
                    'user': username,
                }))


def make_app():
    settings = {
        'cookie_secret': 'Hsdfk2rhfFFGJwefuofjwejf234FJWFN',
        'login_url': '/login',
        'xsrf_cookies': False,
        'debug': False
    }

    return Application([
        (r'/', MainHandler),
        (r"/registration", RegistrationHandler),
        (r"/login", LoginHandler),
        (r"/websocket", ChatSocketHandler)
    ], **settings)


if __name__ == "__main__":
    app = make_app()
    app.listen(8000)
    IOLoop.current().start()

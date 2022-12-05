import socket
import threading
import json
import os
import requests
import re
import time
import traceback
import base64
import random
import sys
from io import BytesIO
from PIL import Image
class Consts:
    BUFFER_SIZE = 1048576
    ADDRESS_SEND_HOST = '127.0.0.1:5700'
    ADDRESS_SEND_PRIVATE = f'http://{ADDRESS_SEND_HOST}/send_private_msg?user_id=%s&message=%s'
    ADDRESS_SEND_GROUP = f'http://{ADDRESS_SEND_HOST}/send_group_msg?group_id=%s&message=%s'
    ADDRESS_RECALL_MESSAGE = f'http://{ADDRESS_SEND_HOST}/delete_msg?message_id=%s'
    ADDRESS_RECV = ('', 5701)
    RE_USERNAME = re.compile(r'[A-Za-z0-9_]{1,16}')
    RE_UUID = re.compile(r'([A-Fa-f0-9]{32})|([A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12})')
    RE_QQNUMBER = re.compile(r'\d{5,}')
    RE_GUILDNAME = re.compile(r'[A-Za-z0-9\x20]{1,32}')
    RE_NEWLINE = re.compile(r'[\n\x20]*\n[\n\x20]*')
    RE_STYLE = re.compile(r'\u00a7.')
    PREFIX = f'[__INTERNALPREFIX{time.time()}__]'
    DEFAULT_SHOP = \
        'wool,stone_sword,chainmail_boots,null,bow,speed_ii_potion_(45_seconds),tnt,' \
        'oak_wood_planks,iron_sword,iron_boots,shears,arrow,invisibility_potion_(30_seconds),water_bucket,' \
        'null,null,null,null,null,null,null'
    DEFAULT_SLOTS = 'Melee,null,null,null,null,null,null,null,Compass'
class Utils:
    @staticmethod
    def _recv_all(sock):
        buffer = b''
        while True:
            data = sock.recv(Consts.BUFFER_SIZE)
            buffer += data
            if len(data) != Consts.BUFFER_SIZE:
                break
        return buffer
    @staticmethod
    def _send(url):
        response = requests.get(url, headers={'Host': Consts.ADDRESS_SEND_HOST})
        if response.status_code != 200:
            traceback.print_stack()
            print(f'Send Message Error (HTTP {response.status_code})!', file=sys.stderr)
            print(f'(URL: {url})', file=sys.stderr)
        json_obj = json.loads(response.content.decode())
        return json_obj.get('data', {}).get('message_id', 0)
    @staticmethod
    def send_private(number, message):
        if not message: return
        return Utils._send(Consts.ADDRESS_SEND_PRIVATE % (number, HttpRequest.encode(message)))
    @staticmethod
    def send_group(number, message):
        if not message: return
        return Utils._send(Consts.ADDRESS_SEND_GROUP % (number, HttpRequest.encode(message)))
    @staticmethod
    def recall_message(message):
        return Utils._send(Consts.ADDRESS_RECALL_MESSAGE % message)
    @staticmethod
    def processor(main):
        def _processor(request, response):
            try:
                message = json.loads(request.data.decode('utf-8'))
                if message['post_type'] == 'message':
                    message_obj = Message(main, message=message)
                    thread = threading.Thread(target=main.process, args=(message_obj,))
                    thread.daemon = True
                    thread.start()
            except Exception:
                pass
        return _processor
    @staticmethod
    def start_listener(main):
        HttpServer(Consts.ADDRESS_RECV, processor=Utils.processor(main)).start()
    @staticmethod
    def copy(obj):
        return json.loads(json.dumps(obj))
    @staticmethod
    def time_to_string_ms(time_):
        localtime = time.localtime(time_ // 1000)
        return '%d.%d.%d-%d:%02d:%02d.%03d' % (
            localtime.tm_year,
            localtime.tm_mon,
            localtime.tm_mday,
            localtime.tm_hour,
            localtime.tm_min,
            localtime.tm_sec,
            time_ % 1000
        )
    @staticmethod
    def time_to_string(time_):
        localtime = time.localtime(time_)
        return '%d.%d.%d-%d:%02d:%02d.%03d' % (
            localtime.tm_year,
            localtime.tm_mon,
            localtime.tm_mday,
            localtime.tm_hour,
            localtime.tm_min,
            localtime.tm_sec,
            time_ % 1000
        )
    @staticmethod
    def period_to_string(time_):
        seconds = time_ % 60
        minutes = time_ // 60 % 60
        hours = time_ // 3600 % 24
        days = time_ // 86400
        if (time_ == 0):
            return '0秒'
        return (f'{days}天' if days else '') + \
                (f'{hours}小时' if hours else '') + \
                (f'{minutes}分钟' if minutes else '') + \
                (f'{seconds}秒' if seconds else '')
    @staticmethod
    def string_to_camel(string):
        l = string.split('_')
        r = []
        for s in l:
            s = s[:1].upper() + s[1:].lower()
            r.append(s)
        return ' '.join(r)
    @staticmethod
    def get(map_, path, default=None):
        try:
            if map_ is None:
                return default
            index_list = path.split('.')
            current = map_
            for index in index_list:
                current = current.get(index, None)
                if current is None:
                    return default
            return current
        except Exception:
            pass
        return default
    @staticmethod
    def set(map_, path, value):
        try:
            if map_ is None:
                return
            *index_list, index_set = path.split('.')
            current = map_
            for index in index_list:
                current = current.setdefault(index, {})
            current[index_set] = value
        except Exception:
            pass
    @staticmethod
    def last(*objects):
        if objects:
            return objects[-1]
        return None
    @staticmethod
    def reset_style(string):
        return ''.join(Consts.RE_STYLE.split(string))
    @staticmethod
    def format(main, message, *values):
        value_list = []
        value_a = 0
        value_b = 0
        for value_name in values:
            for placeholder, placeholder_value in message.placeholders.items():
                value_name = value_name.replace(placeholder, placeholder_value)
            do_append = True
            if value_name.startswith('?'):
                do_append = False
                value_name = value_name[1:]
            if value_name == '/' or value_name == '%':
                if value_b == 0:
                    value = value_a
                else:
                    value = value_a / value_b
                if value_name == '%':
                    value *= 100.0
            else:
                default = 0
                time_format = None
                string_format = None
                if value_name.endswith('?'):
                    default = '?'
                    value_name = value_name[:-1]
                elif value_name.endswith('$'):
                    default = False
                    value_name = value_name[:-1]
                if value_name.endswith('~'):
                    time_format = Utils.time_to_string
                    value_name = value_name[:-1]
                elif value_name.endswith('*'):
                    time_format = Utils.time_to_string_ms
                    value_name = value_name[:-1]
                elif value_name.endswith('&'):
                    time_format = Utils.period_to_string
                    value_name = value_name[:-1]
                elif value_name.endswith('^'):
                    string_format = Utils.string_to_camel
                    value_name = value_name[:-1]
                value = message.get(value_name, default)
                if time_format is not None and isinstance(value, int):
                    value = time_format(value)
                elif string_format is not None and isinstance(value, str):
                    value = string_format(value)
            if isinstance(value, bool):
                value = '是' if value else '否'
            elif isinstance(value, int):
                value_a, value_b = value_b, value
                value = f'{value:,d}'
            elif isinstance(value, float):
                value_a, value_b = value_b, value
                value = f'{value:,.3f}'
            if do_append:
                value_list.append(value)
        return tuple(value_list)
    @staticmethod
    def format_shop(map_, line):
        return '\n' + ' '.join(map(lambda x: map_.get(x, '?'), line))
    @staticmethod
    def escape_bracket(func):
        def _(*args, **kwargs):
            quit, output = func(*args, **kwargs)
            output = str(output)
            output = output.replace('[', '&#91;')
            output = output.replace(']', '&#93;')
            return quit, output
        return _
    @staticmethod
    def get_level(exp, levels):
        level_count = len(levels)
        *levels, last_level = levels
        levels_total_exp = sum(map(lambda x: x[0], levels))
        if exp >= levels_total_exp:
            return int(level_count + (exp - levels_total_exp) // last_level[0]), int((exp - levels_total_exp) % last_level[0]), last_level[1]
        else:
            ret_level = 0
            ret_exp = exp
            ret_full_exp = '0'
            total_level_exp = 0
            for level, (level_exp, level_exp_name) in enumerate(levels):
                total_level_exp += level_exp
                if exp >= total_level_exp:
                    ret_exp = exp - total_level_exp
                else:
                    ret_level = level + 1
                    ret_full_exp = level_exp_name
                    break
            return int(ret_level), int(ret_exp), ret_full_exp
    @staticmethod
    def get_image(binary, crop=None):
        bytesio = BytesIO(binary)
        image = Image.open(bytesio)
        image = image.convert('RGB')
        image = image.resize((92, 44), resample=Image.Resampling.NEAREST)
        if crop is not None:
            image = image.crop(crop)
        return image
class BotException(Exception):
    def __init__(self, reason):
        if isinstance(reason, BotException):
            reason = reason.reason
        super().__init__(reason)
        self.reason = reason
class HttpRequest:
    def __init__(self, method='GET', url='/', headers=None, data=b''):
        self.method = method
        self.url = url
        self.headers = {} if headers is None else headers
        self.data = data
    def set_method(self, method):
        self.method = method
        return self
    def set_url(self, url):
        self.url = url
        return self
    def set_header(self, key, value):
        self.headers[key] = value
        return self
    def set_data(self, data):
        self.data = data
        return self
    def get_header(self, key):
        return self.headers.get(key, None)
    def to_bytes(self):
        lines = []
        lines.append(f'{self.method} {self.url} HTTP/1.1')
        for key, value in self.headers.items():
            lines.append(f'{key}: {value}')
        lines.append('')
        lines.append('')
        return '\r\n'.join(lines).encode('utf-8') + self.data
    @classmethod
    def from_bytes(cls, data):
        request = HttpRequest()
        data, request.data = data.split(b'\r\n\r\n', 1)
        line, *headers = data.decode('utf-8').split('\r\n')
        request.method, request.url, *_ = line.split(' ')
        for header in headers:
            key, value = header.split(':', 1)
            request.set_header(key.strip(), value.strip())
        return request
    @staticmethod
    def encode(string):
        if isinstance(string, str):
            string = string.encode('utf-8')
        return ''.join('%%%02X' % x for x in string)
class HttpResponse:
    def __init__(self, status=200, description='OK', headers=None, data=b''):
        self.status = status
        self.description = description
        self.headers = {} if headers is None else headers
        self.data = data
    def set_status(self, status):
        self.status = status
        return self
    def set_description(self, description):
        self.description = description
        return self
    def set_header(self, key, value):
        self.headers[key] = value
        return self
    def set_data(self, data):
        self.data = data
        return self
    def get_header(self, key):
        return self.headers.get(key, None)
    def to_bytes(self):
        lines = []
        lines.append(f'HTTP/1.1 {self.status} {self.description}')
        for key, value in self.headers.items():
            lines.append(f'{key}: {value}')
        lines.append('')
        lines.append('')
        return '\r\n'.join(lines).encode('utf-8') + self.data
    @classmethod
    def from_bytes(cls, data):
        response = HttpResponse()
        data, response.data = data.split(b'\r\n\r\n', 1)
        line, *headers = data.decode('utf-8').split('\r\n')
        _, response.status, response.description = line.split(' ')
        response.status = int(response.status)
        for header in headers:
            key, value = header.split(':', 1)
            response.set_header(key.strip(), value.strip())
        return response
class HttpServer:
    def __init__(self, address, backlog=5, processor=None):
        self.address = address
        self.backlog = backlog
        self.processor = self.process if processor is None else processor
        self.thread = None
        self.started = False
    def process(self, request, response):
        pass
    def _accept(self, sock, address):
        request = HttpRequest.from_bytes(Utils._recv_all(sock))
        response = HttpResponse()
        self.processor(request, response)
        sock.sendall(response.to_bytes())
        sock.close()
    def _run(self):
        try:
            self.started = True
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(self.address)
            sock.listen(self.backlog)
            while True:
                client, address = sock.accept()
                thread = threading.Thread(
                    target=self._accept, args=(client, address))
                thread.daemon = True
                thread.start()
        except Exception:
            pass
        self.started = False
    def start(self, block=False):
        if not self.started:
            if block:
                self._run()
            else:
                self.thread = threading.Thread(target=self._run)
                self.thread.daemon = True
                self.thread.start()
class Options:
    def __init__(self, file_name, default_options):
        self.file_name = file_name
        self.default_options = Utils.copy(default_options)
        self.options = default_options
        self._read_options()
        self.write_options()
    def _read_options(self):
        if os.path.exists(self.file_name):
            with open(self.file_name, 'r') as fr:
                self.options = json.loads(fr.read())
    def write_options(self):
        with open(self.file_name, 'w') as fw:
            fw.write(json.dumps(self.options))
    def get(self, path, default=None):
        return Utils.get(self.options, path, default=default)
    def set(self, path, value):
        Utils.set(self.options, path, value)
        self.write_options()
class Message:
    def __init__(self, main, message=None, group=-1, user=10001, id=0, raw_message=''):
        if message is None:
            self.group = group
            self.user = user
            self.id = id
            self.message = raw_message
        else:
            if message['message_type'] == 'group':
                self.group = message['group_id']
            else:
                self.group = -1
            self.user = message['user_id']
            self.id = message['message_id']
            self.message = message['raw_message']
        self.args = self.message.split()
        self.data = {
            'prefix': main.options.get(f'global.prefixes.{self.group}', main.options.get(f'global.prefixes.default', '/')),
            'args': dict(zip(map(str, range(len(self.args))), self.args)),
            'apiset': main.options.get(f'global.apisets.{main.options.get("global.using_apiset")}')
        }
        self.placeholders = {}
    def send(self, main, message):
        message = str(message)
        if main.options.get('global.reply_message', False):
            message = self.reply() + message
        message_id = 0
        if self.group == -1:
            message_id = Utils.send_private(self.user, message)
        else:
            message_id = Utils.send_group(self.group, message)
        return message_id
    def reply(self):
        return f'[CQ:reply,id={self.id}]'
    def at(self):
        return f'[CQ:at,qq={self.user}]'
    def get(self, path, default=None):
        return Utils.get(self.data, path, default=default)
    def set(self, path, value):
        Utils.set(self.data, path, value)
class Bot:
    def __init__(self, name):
        self.name = name
    def _have_permission_single(self, number, whitelist, blacklist, default):
        if number in blacklist:
            return False
        elif number in whitelist:
            return True
        else:
            return default == 'whitelist'
    def have_permission(self, main, message):
        group_whitelist = []
        group_blacklist = []
        user_whitelist = []
        user_blacklist = []
        group_default = 'whitelist'
        user_default = 'whitelist'
        for list_name in main.options.get(f'bots.{self.name}.lists'):
            lst = main.options.get(f'lists.{list_name}', {})
            group_whitelist += lst.get('group_whitelist', [])
            group_blacklist += lst.get('group_blacklist', [])
            user_whitelist += lst.get('user_whitelist', [])
            user_blacklist += lst.get('user_blacklist', [])
            if lst.get('group_default', 'blacklist') != 'whitelist':
                group_default = 'blacklist'
            if lst.get('user_default', 'blacklist') != 'whitelist':
                user_default = 'blacklist'
        if not self._have_permission_single(message.group, group_whitelist, group_blacklist, group_default):
            return False
        if not self._have_permission_single(message.user, user_whitelist, user_blacklist, user_default):
            return False
        return True
    def can_process(self, main, message):
        return False
    def process(self, main, message):
        pass
class BotError(Bot):
    def __init__(self, error):
        self.error = error
    def process(self, *args, **kwargs):
        raise self.error
class BotCommand(Bot):
    def __init__(self, name, commands, pipes, message):
        super().__init__(name)
        self.commands = commands
        self.pipes = pipes
        self.message = message
    def can_process(self, main, message):
        message_lower = message.message.lower()
        message_split = message_lower.split()
        prefix = main.options.get(f'global.prefixes.{message.group}', main.options.get(f'global.prefixes.default', '/'))
        if len(message_split) > 0:
            for command in self.commands:
                if message_split[0] == f'{prefix}{command}' or message_split[0] == Consts.PREFIX + command:
                    return True
        return False
    def process(self, main, message):
        for pipe in self.pipes:
            pipe(main, message)
        reply = self.message(main, message)
        if reply is not None:
            reply = str(reply).strip()
            reply = '\n'.join(Consts.RE_NEWLINE.split(reply))
            message.send(main, reply)
class BotAutoreply(Bot):
    def can_process(self, main, message):
        text = message.message.replace('.', '{:}')
        if main.options.get('options.autoreply.strip', False):
            text = text.strip()
        if main.options.get('options.autoreply.lower', False):
            text = text.lower()
        replies = main.options.get('options.autoreply.replies', {})
        return text in replies
    def process(self, main, message):
        text = message.message.replace('.', '{:}')
        if main.options.get('options.autoreply.strip', False):
            text = text.strip()
        if main.options.get('options.autoreply.lower', False):
            text = text.lower()
        replies = main.options.get('options.autoreply.replies', {})
        reply = replies.get(text, None)
        if reply:
            random.seed(time.time())
            reply = random.choice(reply)
            reply = reply.replace('{<}', '[')
            reply = reply.replace('{>}', ']')
            reply = reply.replace('{group}', str(message.group))
            reply = reply.replace('{user}', str(message.user))
            reply = reply.replace('{id}', str(message.id))
            reply = reply.replace('{message}', message.message)
            message.send(main, reply)
class Maps:
    def _mode(mode_map, prefix, mode_prefix, bridge_prefix, description, *aliases):
        mode_prefix = prefix + mode_prefix
        bridge_prefix = prefix + bridge_prefix
        for alias in aliases:
            mode_map[alias] = (mode_prefix, bridge_prefix, description)
    _BW = 'api_hypixel_player.player.stats.Bedwars.'
    MODE_BEDWARS = {None: (_BW, '', '')}
    def _dream(mode_func, mode_map, prefix, name, description, short):
        mode_func(mode_map, prefix, f'eight_two_{name}_', '', f'双人{description}模式', f'eight_two_{name}', f'8_2_{name}', f'{short}2', f'{name}2')
        mode_func(mode_map, prefix, f'four_four_{name}_', '', f' 4v4v4v4 {description}模式', f'four_four_{name}', f'4_4_{name}', f'{short}4', f'{name}4', f'{name}')
    _mode(MODE_BEDWARS, _BW, '', '', '', '', 'a', 'all', 'overall')
    _mode(MODE_BEDWARS, _BW, 'eight_one_', '', '单人模式', 'eight_one', 'solo', 'solos', '1', '1s', '81', '1v1', '8_1')
    _mode(MODE_BEDWARS, _BW, 'eight_two_', '', '双人模式', 'eight_two', 'double', 'doubles', '2', '2s', '82', '2v2', '8_2')
    _mode(MODE_BEDWARS, _BW, 'four_three_', '', ' 3v3v3v3 ', 'four_three', 'three', 'threes', '3', '3s', '43', '3v3', '3v3v3v3', '3333', '4_3')
    _mode(MODE_BEDWARS, _BW, 'four_four_', '', ' 4v4v4v4 ', 'four_four', 'four', 'fours', '4', '4s', '44', '4v4v4v4', '4444', '4_4')
    _mode(MODE_BEDWARS, _BW, 'two_four_', '', ' 4v4 ', 'two_four', '4v4', '24', '2_4')
    _mode(MODE_BEDWARS, _BW, 'castle_', '', ' 40v40 城池攻防战模式', 'castle', 'two_forty', '40', '240', '40v40')
    _dream(_mode, MODE_BEDWARS, _BW, 'voidless', '无虚空', 'v')
    _dream(_mode, MODE_BEDWARS, _BW, 'armed', '枪战', 'a')
    _dream(_mode, MODE_BEDWARS, _BW, 'swap', '交换', 's')
    _dream(_mode, MODE_BEDWARS, _BW, 'rush', '疾速', 'r')
    _dream(_mode, MODE_BEDWARS, _BW, 'ultimate', '超能力', 'u')
    _dream(_mode, MODE_BEDWARS, _BW, 'lucky', '幸运方块', 'l')
    _dream(_mode, MODE_BEDWARS, _BW, 'underworld', 'Underworld', 'uw')
    _DUELS = 'api_hypixel_player.player.stats.Duels.'
    MODE_DUELS = {None: (_DUELS, _DUELS, '')}
    _mode(MODE_DUELS, _DUELS, '', '', '', '', 'a', 'all', 'overall')
    _mode(MODE_DUELS, _DUELS, 'bow_duel_', 'bow_duel_', '弓箭决斗', 'bow_duel', 'bow')
    _mode(MODE_DUELS, _DUELS, 'classic_duel_', 'classic_duel_', '经典决斗', 'classic_duel', 'classic')
    _mode(MODE_DUELS, _DUELS, 'op_duel_', 'op_duel_', '高手决斗', 'op_duel', 'op')
    _mode(MODE_DUELS, _DUELS, 'uhc_duel_', 'uhc_duel_', '极限生存决斗', 'uhc_duel', 'uhc', 'buhc')
    _mode(MODE_DUELS, _DUELS, 'potion_duel_', 'potion_duel_', '药水决斗', 'potion_duel', 'potion', 'nodebuff', 'pot')
    _mode(MODE_DUELS, _DUELS, 'mw_duel_', 'mw_duel_', '超级战墙决斗', 'mw_duel', 'mw', 'megawall', 'megawalls')
    _mode(MODE_DUELS, _DUELS, 'blitz_duel_', 'blitz_duel_', '闪电饥饿游戏决斗', 'blitz_duel', 'blitz', 'bsg')
    _mode(MODE_DUELS, _DUELS, 'sw_duel_', 'sw_duel_', '空岛战争决斗', 'sw_duel', 'sw', 'skywar', 'skywars')
    _mode(MODE_DUELS, _DUELS, 'combo_duel_', 'combo_duel_', '连击决斗', 'combo_duel', 'combo')
    _mode(MODE_DUELS, _DUELS, 'bowspleef_duel_', 'bowspleef_duel_', '掘一死箭决斗', 'bowspleef_duel', 'bowspleef')
    _mode(MODE_DUELS, _DUELS, 'sumo_duel_', 'sumo_duel_', '相扑决斗', 'sumo_duel', 'sumo')
    _mode(MODE_DUELS, _DUELS, 'boxing_duel_', 'boxing_duel_', ' Boxing 决斗', 'boxing_duel', 'boxing')
    _mode(MODE_DUELS, _DUELS, 'bridge_duel_', 'bridge_duel_bridge_', '战桥决斗', 'bridge_duel', 'bridge')
    _mode(MODE_DUELS, _DUELS, 'uhc_doubles_', 'uhc_doubles_', '极限生存双人模式', 'uhc_doubles', 'uhc2')
    _mode(MODE_DUELS, _DUELS, 'uhc_four_', 'uhc_four_', '极限生存四人模式', 'uhc_four', 'uhc4')
    _mode(MODE_DUELS, _DUELS, 'sw_doubles_', 'sw_doubles_', '空岛战争双人模式', 'sw_doubles', 'sw2', 'skywar2', 'skywars2')
    _mode(MODE_DUELS, _DUELS, 'mw_doubles_', 'mw_doubles_', '超级战墙双人模式', 'mw_doubles', 'mw2', 'megawall2', 'megawalls2')
    _mode(MODE_DUELS, _DUELS, 'op_doubles_', 'op_doubles_', '高手双人模式', 'op_doubles', 'op2')
    _mode(MODE_DUELS, _DUELS, 'bridge_doubles_', 'bridge_doubles_bridge_', '战桥双人模式', 'bridge_doubles', 'bridge2')
    _mode(MODE_DUELS, _DUELS, 'bridge_threes_', 'bridge_threes_bridge_', '战桥三人模式', 'bridge_threes', 'bridge3')
    _mode(MODE_DUELS, _DUELS, 'bridge_four_', 'bridge_four_bridge_', '战桥四人模式', 'bridge_four', 'bridge4')
    _mode(MODE_DUELS, _DUELS, 'bridge_2v2v2v2_', 'bridge_2v2v2v2_bridge_', '战桥 2v2v2v2 模式', 'bridge_2v2v2v2', 'bridge42')
    _mode(MODE_DUELS, _DUELS, 'bridge_3v3v3v3_', 'bridge_3v3v3v3_bridge_', '战桥 3v3v3v3 模式', 'bridge_3v3v3v3', 'bridge43')
    _mode(MODE_DUELS, _DUELS, 'capture_threes_', 'capture_threes_bridge_', '战桥 CTF 三人模式', 'capture_threes', 'capture', 'ctf')
    _mode(MODE_DUELS, _DUELS, 'uhc_meetup_', 'uhc_meetup_', '极限生存死亡竞赛', 'uhc_meetup', 'uhc_meetup', 'uhc_deathmatch')
    _mode(MODE_DUELS, _DUELS, 'parkour_eight_', 'parkour_eight_', '跑酷决斗', 'parkour_eight', 'parkour')
    _mode(MODE_DUELS, _DUELS, 'duel_arena_', 'duel_arena_', '竞技场模式', 'duel_arena', 'arena')
    FAVORITE = {
        'null': '空',
        'wool': '羊毛',
        'hardened_clay': '粘土',
        'blast-proof_glass': '玻璃',
        'end_stone': '末地石',
        'ladder': '梯子',
        'oak_wood_planks': '木板',
        'obsidian': '黑曜石',
        'stone_sword': '石剑',
        'iron_sword': '铁剑',
        'diamond_sword': '钻石剑',
        'stick_(knockback_i)': '击退棒',
        'chainmail_boots': '锁链套',
        'iron_boots': '铁套',
        'diamond_boots': '钻石套',
        'shears': '剪刀',
        'wooden_pickaxe': '镐',
        'wooden_axe': '斧',
        'arrow': '箭',
        'bow': '弓',
        'bow_(power_i)': '力量弓',
        'bow_(power_i__punch_i)': '冲击弓',
        'speed_ii_potion_(45_seconds)': '速度',
        'jump_v_potion_(45_seconds)': '跳跃',
        'invisibility_potion_(30_seconds)': '隐身',
        'golden_apple': '金苹果',
        'bedbug': '床虱',
        'dream_defender': '铁傀儡',
        'fireball': '火球',
        'tnt': 'TNT',
        'ender_pearl': '珍珠',
        'water_bucket': '水桶',
        'bridge_egg': '搭桥蛋',
        'magic_milk': '牛奶',
        'sponge': '海绵',
        'compact_pop-up_tower': '速建塔',
        'magnum': '马格南手枪',
        'rifle': '步枪',
        'smg': 'SMG',
        'not-a-flamethrower': '不是喷火器',
        'shotgun': '霰弹枪',
        'Melee': '剑',
        'Tools': '工具',
        'Ranged': '弓',
        'Utility': '道具',
        'Blocks': '方块',
        'Potions': '药水',
        'Compass': '指南针'
    }
    SKYWARS_LEVELS = (
        (20, '20'),
        (50, '50'),
        (80, '80'),
        (100, '100'),
        (250, '250'),
        (500, '500'),
        (1000, '1k'),
        (1500, '1.5k'),
        (2500, '2.5k'),
        (4000, '4k'),
        (5000, '5k'),
        (10000, '10k')
    )
    SKYWARS_STAR = {
        'default': '\u22c6',
        'angel_1': '\u2605',
        'angel_2': '\u2606',
        'angel_3': '\u263c',
        'angel_4': '\u2736',
        'angel_5': '\u2733',
        'angel_6': '\u2734',
        'angel_7': '\u2737',
        'angel_8': '\u274b',
        'angel_9': '\u273c',
        'angel_10': '\u2742',
        'angel_11': '\u2741',
        'angel_12': '\u262c',
        'iron_prestige': '\u2719',
        'gold_prestige': '\u2764',
        'diamond_prestige': '\u2620',
        'emerald_prestige': '\u2726',
        'sapphire_prestige': '\u270c',
        'ruby_prestige': '\u2766',
        'crystal_prestige': '\u2735',
        'opal_prestige': '\u2763',
        'amethyst_prestige': '\u262f',
        'rainbow_prestige': '\u273a',
        'mythic_prestige': '\u0ca0_\u0ca0',
        'favor_icon': '\u2694',
        'omega_icon': '\u03a9'
    }
    RANK = {
        'ADMIN': '[ADMIN] ',
        'GAME_MASTER': '[GM] ',
        'YOUTUBER': '[YOUTUBE] ',
        'SUPERSTAR': '[MVP++] ',
        'VIP': '[VIP] ',
        'VIP_PLUS': '[VIP+] ',
        'MVP': '[MVP] ',
        'MVP_PLUS': '[MVP+] '
    }
    CAPE = {
        'http://textures.minecraft.net/texture/2340c0e03dd24a11b15a8b33c2a7e9e32abb2051b2481d0ba7defd635ca7a933': 'Migrator 迁移披风 (http://textures.minecraft.net/texture/2340c0e03dd24a11b15a8b33c2a7e9e32abb2051b2481d0ba7defd635ca7a933)',
        'http://textures.minecraft.net/texture/f9a76537647989f9a0b6d001e320dac591c359e9e61a31f4ce11c88f207f0ad4': 'Vanilla 双版本披风 (http://textures.minecraft.net/texture/f9a76537647989f9a0b6d001e320dac591c359e9e61a31f4ce11c88f207f0ad4)',
        'http://textures.minecraft.net/texture/e7dfea16dc83c97df01a12fabbd1216359c0cd0ea42f9999b6e97c584963e980': 'Minecon 2016 末影人披风 (http://textures.minecraft.net/texture/e7dfea16dc83c97df01a12fabbd1216359c0cd0ea42f9999b6e97c584963e980)',
        'http://textures.minecraft.net/texture/b0cc08840700447322d953a02b965f1d65a13a603bf64b17c803c21446fe1635': 'Minecon 2015 铁傀儡披风 (http://textures.minecraft.net/texture/b0cc08840700447322d953a02b965f1d65a13a603bf64b17c803c21446fe1635)',
        'http://textures.minecraft.net/texture/153b1a0dfcbae953cdeb6f2c2bf6bf79943239b1372780da44bcbb29273131da': 'Minecon 2013 活塞披风 (http://textures.minecraft.net/texture/153b1a0dfcbae953cdeb6f2c2bf6bf79943239b1372780da44bcbb29273131da)',
        'http://textures.minecraft.net/texture/a2e8d97ec79100e90a75d369d1b3ba81273c4f82bc1b737e934eed4a854be1b6': 'Minecon 2012 金镐披风 (http://textures.minecraft.net/texture/a2e8d97ec79100e90a75d369d1b3ba81273c4f82bc1b737e934eed4a854be1b6)',
        'http://textures.minecraft.net/texture/953cac8b779fe41383e675ee2b86071a71658f2180f56fbce8aa315ea70e2ed6': 'Minecon 2011 苦力怕披风 (http://textures.minecraft.net/texture/953cac8b779fe41383e675ee2b86071a71658f2180f56fbce8aa315ea70e2ed6)',
        'http://textures.minecraft.net/texture/9e507afc56359978a3eb3e32367042b853cddd0995d17d0da995662913fb00f7': 'Mojang Studios 披风 (http://textures.minecraft.net/texture/9e507afc56359978a3eb3e32367042b853cddd0995d17d0da995662913fb00f7)',
        'http://textures.minecraft.net/texture/5786fe99be377dfb6858859f926c4dbc995751e91cee373468c5fbf4865e7151': 'Mojang 披风 (http://textures.minecraft.net/texture/5786fe99be377dfb6858859f926c4dbc995751e91cee373468c5fbf4865e7151)'
    }
    PREFIX_COLOR = {
        'GOLD': '金色',
        'AQUA': '青色'
    }
    PLUS_COLOR = {
        'RED': '浅红色 (默认)',
        'GOLD': '金色 (35 级)',
        'GREEN': '浅绿色 (45 级)',
        'YELLOW': '黄色 (55 级)',
        'LIGHT_PURPLE': '粉色 (65 级)',
        'WHITE': '白色 (75 级)',
        'BLUE': '浅蓝色 (85 级)',
        'DARK_GREEN': '深绿色 (95 级)',
        'DARK_RED': '深红色 (150 级)',
        'DARK_AQUA': '青色 (150 级)',
        'DARK_PURPLE': '紫色 (200 级)',
        'DARK_GRAY': '灰色 (200 级)',
        'BLACK': '黑色 (250 级)',
        'DARK_BLUE': '深蓝色 (100 Rank)'
    }
    GUILD_TAG_COLOR = {
        None: '无标签',
        'GRAY': '灰色 (默认)',
        'GOLD': '金色 (MVP++)',
        'DARK_AQUA': '青色 (15 级)',
        'DARK_GREEN': '绿色 (25 级)',
        'YELLOW': '黄色 (45 级)'
    }
    GUILD_LEVELS = (
        (100000, '100k'),
        (150000, '150k'),
        (250000, '250k'),
        (500000, '500k'),
        (750000, '750k'),
        (1000000, '1m'),
        (1250000, '1.25m'),
        (1500000, '1.5m'),
        (2000000, '2m'),
        (2500000, '2.5m'),
        (2500000, '2.5m'),
        (2500000, '2.5m'),
        (2500000, '2.5m'),
        (2500000, '2.5m'),
        (3000000, '3m')
    )
    OFCAPE_DESIGN = {
        '852C2C5E1C1CE29F00441616': 'Standard',
        'F8F8F8DDDDDDFFFFFFC8C8C8': 'White',
        '8585855E5E5ECECECE444444': 'Gray',
        '1E1E1E010101404040202020': 'Black',
        '8500005E0000E20000440000': 'Red',
        '008500005E0000E200004400': 'Green',
        '00008500005E4040FF000044': 'Blue',
        'F2F200CACA00FFFF00BEBE00': 'Yellow',
        '8500855E005EE200E2440044': 'Purple',
        '008585005E5E00E2E2004444': 'Cyan'
    }
    OFCAPE_ALIGN = {
        's': 'Scale',
        't': 'Top',
        'm': 'Middle',
        'b': 'Bottom'
    }
class Pipes:
    LAST_COMMAND = 0.0
    @staticmethod
    def cooldown(main, message):
        if message.user not in main.options.get('global.bypass_cooldown', []):
            now_time = time.time()
            if now_time > Pipes.LAST_COMMAND + main.options.get('global.cooldown_time'):
                Pipes.LAST_COMMAND = now_time
            else:
                raise BotException('使用指令过快!')
    @staticmethod
    def _api(name, requester, response_processor, *args):
        def _(main, message):
            api_url = message.get(f'apiset.{name}', '')
            url_args = tuple([message.get(arg, '') for arg in args])
            if len(url_args) == 0:
                url = api_url
            elif len(url_args) == 1:
                url = api_url % url_args[0]
            else:
                url = api_url % url_args
            response = requester(url, headers={'User-Agent': message.get('user_agent', '')})
            data = response_processor(response)
            message.data['api_%s' % name] = data
        return _
    @staticmethod
    def _api_status(name, response, code=200):
        if response.status_code != code:
            raise BotException('API %s 查询失败! (HTTP %d)' % (name, response.status_code))
    @staticmethod
    def api(name, success_flag=None, test_key=None, *args):
        def _(response):
            Pipes._api_status(name, response, 200)
            data = json.loads(response.content.decode('utf-8'))
            if success_flag is not None:
                if not Utils.get(data, success_flag, False):
                    raise BotException('API %s 查询失败! (Failed)' % name)
            if test_key is not None:
                if Utils.get(data, test_key) is None:
                    raise BotException('API %s 查询失败! (None)' % name)
            return data
        return Pipes._api(name, requests.get, _, *args)
    @staticmethod
    def api_binary(name, *args):
        def _(response):
            Pipes._api_status(name, response, 200)
            return response.content
        return Pipes._api(name, requests.get, _, *args)
    @staticmethod
    def api_optifine_format():
        def _requester(url, headers):
            url, name = url.split('&&')
            return requests.post(url, data=f'username={name}', headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'}, allow_redirects=False)
        def _processer(response):
            if response.status_code != 302:
                return None
            location = response.headers.get('Location', '')
            index_equal = location.find('=')
            index_and = location.find('&')
            if not location or index_equal == -1 or index_and == -1 or index_equal >= index_and:
                return None
            return location[index_equal + 1:index_and]
        return Pipes._api('optifine_format', _requester, _processer, 'api_mojang_profile.name')
    @staticmethod
    def re_expression(exp, arg, error_msg):
        def _(main, message):
            value = message.get(arg)
            if not isinstance(value, str) or not exp.fullmatch(value):
                raise BotException(error_msg)
        return _
    @staticmethod
    def replace(mapping):
        def _(main, message):
            message.placeholders.update(mapping)
        return _
    @staticmethod
    def plus(value_a, value_b, result):
        def _(main, message):
            message.set(result, message.get(value_a, 0) + message.get(value_b, 0))
        return _
    @staticmethod
    def game_mode(mode_map, mode_arg, arg='args.2', placeholder='!', placeholder_bridge='`'):
        def _(main, message):
            mode_name = message.get(arg, None)
            if mode_name in mode_map:
                mode = mode_map[mode_name]
                message.placeholders[placeholder] = mode[0]
                message.placeholders[placeholder_bridge] = mode[1]
                message.set(mode_arg, mode[2])
            else:
                raise BotException('未知的模式!')
        return _
    @staticmethod
    def session(main, message):
        uuid = message.get('api_mojang_session.id', '?' * 32)
        properties = message.get('api_mojang_session.properties', [])
        message.set('session.id_dashed', f'{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}')
        for property in properties:
            if property.get('name', '') == 'textures':
                value = json.loads(base64.b64decode(property.get('value', '')).decode())
                message.set('session.skin', Utils.get(value, 'textures.SKIN.url', '默认'))
                if Utils.get(value, 'textures.SKIN.metadata.model') == 'slim':
                    message.set('session.model', '纤细 (Alex)')
                else:
                    message.set('session.model', '默认 (Steve)')
                cape = Utils.get(value, 'textures.CAPE.url')
                if cape is None:
                    message.set('session.cape', '无')
                else:
                    cape = Maps.CAPE.get(cape, cape)
                    message.set('session.cape', cape)
                break
    @staticmethod
    def hypixel(main, message):
        uuid = message.get('api_mojang_profile.id')
        username = message.get('api_hypixel_player.player.displayname')
        username_mojang = message.get('api_mojang_profile.name')
        custom_rank = main.options.get(f'options.hypixel.ranks.{uuid}')
        rank = ''
        rank_raw = 'NONE'
        rank_prefix = message.get('api_hypixel_player.player.prefix')
        rank_rank = message.get('api_hypixel_player.player.rank')
        rank_monthly = message.get('api_hypixel_player.player.monthlyPackageRank')
        rank_new = message.get('api_hypixel_player.player.newPackageRank')
        rank_package = message.get('api_hypixel_player.player.packageRank')
        if rank_prefix is not None:
            rank, rank_raw = Utils.reset_style(rank_prefix) + ' ', 'CUSTOM'
        elif rank_rank in Maps.RANK:
            rank, rank_raw = Maps.RANK[rank_rank], rank_rank
        elif rank_monthly in Maps.RANK:
            rank, rank_raw = Maps.RANK[rank_monthly], rank_monthly
        elif rank_new in Maps.RANK:
            rank, rank_raw = Maps.RANK[rank_new], rank_new
        elif rank_package in Maps.RANK:
            rank, rank_raw = Maps.RANK[rank_package], rank_package
        if custom_rank is not None:
            rank = custom_rank.replace('{rank}', rank)
        message.set('hypixel.name', rank + username)
        message.set('hypixel.rank_raw', rank_raw)
        if username != username_mojang:
            message.set('hypixel.name_change', f'\n此玩家已改名! ({username} -> {username_mojang})')
        else:
            message.set('hypixel.name_change', '')
    @staticmethod
    def command_hypixel(main, message):
        rank_raw = message.get('hypixel.rank_raw', 'NONE')
        hypixel_exp = message.get('api_hypixel_player.player.networkExp', 0.0)
        hypixel_level = (0.0008 * hypixel_exp + 12.25) ** 0.5 - 2.5
        rank_prefix_color = message.get('api_hypixel_player.player.monthlyRankColor', 'GOLD')
        rank_plus_color = message.get('api_hypixel_player.player.rankPlusColor', 'RED')
        rank_color_line = ''
        if rank_raw == 'MVP_PLUS':
            rank_color_line = f'\nMVP+ 颜色: {Maps.PLUS_COLOR.get(rank_plus_color, rank_plus_color)}'
        elif rank_raw == 'SUPERSTAR':
            rank_color_line = f'\nMVP 颜色: {Maps.PREFIX_COLOR.get(rank_prefix_color, rank_prefix_color)} | ++ 颜色: {Maps.PLUS_COLOR.get(rank_plus_color, rank_plus_color)}'
        message.set('hypixel.level', hypixel_level)
        message.set('hypixel.rank_color', rank_color_line)
    @staticmethod
    def command_bedwars(main, message):
        bedwars_total_exp = message.get('api_hypixel_player.player.stats.Bedwars.Experience', 0)
        bedwars_level = 100 * (bedwars_total_exp // 487000)
        bedwars_exp = 0
        bedwars_full_exp = '0'
        bedwars_total_exp %= 487000
        if bedwars_total_exp < 500:
            bedwars_level, bedwars_exp, bedwars_full_exp = bedwars_level, bedwars_total_exp, '500'
        elif bedwars_total_exp < 1500:
            bedwars_level, bedwars_exp, bedwars_full_exp = bedwars_level + 1, bedwars_total_exp - 500, '1k'
        elif bedwars_total_exp < 3500:
            bedwars_level, bedwars_exp, bedwars_full_exp = bedwars_level + 2, bedwars_total_exp - 1500, '2k'
        elif bedwars_total_exp < 7000:
            bedwars_level, bedwars_exp, bedwars_full_exp = bedwars_level + 3, bedwars_total_exp - 3500, '3.5k'
        else:
            bedwars_level, bedwars_exp, bedwars_full_exp = bedwars_level + 4 + (bedwars_total_exp - 7000) // 5000, (bedwars_total_exp - 7000) % 5000, '5k'
        bedwars_level = int(bedwars_level)
        bedwars_exp = int(bedwars_exp)
        bedwars_shop = message.get('api_hypixel_player.player.stats.Bedwars.favourites_2', Consts.DEFAULT_SHOP).split(',')
        bedwars_slots = message.get('api_hypixel_player.player.stats.Bedwars.favorite_slots', Consts.DEFAULT_SLOTS).split(',')
        message.set('bedwars.shop',
            Utils.format_shop(Maps.FAVORITE, bedwars_shop[:7]) +
            Utils.format_shop(Maps.FAVORITE, bedwars_shop[7:14]) +
            Utils.format_shop(Maps.FAVORITE, bedwars_shop[14:]))
        message.set('bedwars.slots', Utils.format_shop(Maps.FAVORITE, bedwars_slots))
        message.set('bedwars.level', str(bedwars_level))
        message.set('bedwars.level_int', bedwars_level)
        message.set('bedwars.star', '\u272b' if bedwars_level < 1100 else '\u272a' if bedwars_level < 2100 else '\u269d')
        message.set('bedwars.exp', bedwars_exp)
        message.set('bedwars.full_exp', bedwars_full_exp)
    @staticmethod
    def command_skywars(main, message):
        skywars_total_exp = int(message.get('api_hypixel_player.player.stats.SkyWars.skywars_experience', 0))
        skywars_level = 0
        skywars_exp = skywars_total_exp
        skywars_full_exp = '0'
        skywars_icon = message.get('api_hypixel_player.player.stats.SkyWars.selected_prestige_icon', 'default')
        skywars_corrupt = message.get('api_hypixel_player.player.stats.SkyWars.angel_of_death_level', 0)
        skywars_angels_offering = message.get('api_hypixel_player.player.stats.SkyWars.angels_offering', 0) > 0
        skywars_favor_of_the_angel = 'favor_of_the_angel' in message.get('api_hypixel_player.player.stats.SkyWars.packages', [])
        skywars_corrupt_suffix = ''
        if skywars_angels_offering:
            if skywars_favor_of_the_angel:
                skywars_corrupt_suffix = ' (天使之祭&天使眷顾)'
            else:
                skywars_corrupt_suffix = ' (天使之祭)'
        elif skywars_favor_of_the_angel:
            skywars_corrupt_suffix = ' (天使眷顾)'
        if skywars_angels_offering:
            skywars_corrupt += 1
        if skywars_favor_of_the_angel:
            skywars_corrupt += 1
        skywars_level, skywars_exp, skywars_full_exp = Utils.get_level(skywars_total_exp, Maps.SKYWARS_LEVELS)
        message.set('skywars.level', skywars_level)
        message.set('skywars.exp', skywars_exp)
        message.set('skywars.full_exp', skywars_full_exp)
        message.set('skywars.star', Maps.SKYWARS_STAR.get(skywars_icon, '?'))
        message.set('skywars.corrupt', '%d%%%s' % (skywars_corrupt, skywars_corrupt_suffix))
    @staticmethod
    def command_guild(api):
        def _(main, message):
            members = message.get(f'api_hypixel_guild_{api}.guild.members', [])
            exp = message.get(f'api_hypixel_guild_{api}.guild.exp', 0)
            tag_color = message.get(f'api_hypixel_guild_{api}.guild.tagColor')
            preferred_games = message.get(f'api_hypixel_guild_{api}.guild.preferredGames', [])
            level, guild_exp, full_exp = Utils.get_level(exp, Maps.GUILD_LEVELS)
            level -= 1
            message.set('guild.member_count', len(members))
            message.set('guild.level', level)
            message.set('guild.exp', guild_exp)
            message.set('guild.full_exp', full_exp)
            message.set('guild.double_exp', min(100, level // 3 * 2 + level % 3))
            message.set('guild.double_coins', min(100, level // 3))
            message.set('guild.tag_color', Maps.GUILD_TAG_COLOR.get(tag_color, tag_color))
            message.set('guild.preferred_games', ', '.join([Utils.string_to_camel(game) for game in preferred_games]) if preferred_games else '无')
        return _
    @staticmethod
    def command_guild_player(api):
        def _(main, message):
            members = message.get(f'api_hypixel_guild_{api}.guild.members', [])
            uuid = message.get('api_mojang_profile.id', 'Love')
            for member in members:
                if member.get('uuid', 'Q_TT') == uuid or (member.get('rank', 'CUTE') == 'Guild Master' and uuid == 'Love'):
                    message.set('guild.player', member)
                    message.set('guild.player.exp', dict(zip(map(str, range(7)), map(lambda x: x[1], sorted(member.get('expHistory', {}).items(), key=lambda x: x[0])))))
                    break
        return _
    @staticmethod
    def _check_valign(main, message, valign, binary):
        message.set('ofcape.valign', valign)
        APIs.OPTIFINE_BANNER(main, message)
        image_match = Utils.get_image(message.get('api_optifine_banner'), (2, 2, 22, 34))
        return image_match.tobytes() == binary
    @staticmethod
    def command_optifine_cape(main, message):
        name = message.get('api_mojang_profile.name', '')
        image = Utils.get_image(message.get('api_optifine_cape'))
        image_banner = image.crop((2, 2, 22, 34)).tobytes()
        color_top = ''.join(map('%02X'.__mod__, image.getpixel((22, 2))))
        color_bottom = ''.join(map('%02X'.__mod__, image.getpixel((22, 33))))
        of_format = message.get('api_optifine_format')
        if of_format is None:
            color_text = ''.join(map('%02X'.__mod__, image.getpixel((6, 10))))
            color_shadow = ''.join(map('%02X'.__mod__, image.getpixel((6, 12))))
            colors = color_top + color_bottom + color_text + color_shadow
            message.set('ofcape.design', Maps.OFCAPE_DESIGN.get(colors, 'Custom...'))
            message.set('ofcape.custom', f'\nText: {color_text}\nShadow: {color_shadow}')
            message.set('ofcape.banner', '')
        else:
            valign = 'b'
            message.set('ofcape.url', of_format)
            for va in 'stm':
                if Pipes._check_valign(main, message, va, image_banner):
                    valign = va
                    break
            if not Pipes._check_valign(main, message, valign, image_banner):
                raise BotException('OptiFine 披风查询失败!')
            align = Maps.OFCAPE_ALIGN.get(valign, 'Unknown')
            message.set('ofcape.design', 'Banner...')
            message.set('ofcape.banner', f'\nURL: {of_format}\nAlign: {align}')
            message.set('ofcape.custom', '')
        message.set('ofcape.top', color_top)
        message.set('ofcape.bottom', color_bottom)
class APIs:
    RE_USERNAME = Pipes.re_expression(Consts.RE_USERNAME, 'args.1', '用户名格式错误!')
    RE_UUID = Pipes.re_expression(Consts.RE_UUID, 'args.1', 'UUID 格式错误!')
    RE_QQNUMBER = Pipes.re_expression(Consts.RE_QQNUMBER, 'args.1', 'QQ 号码格式错误!')
    RE_GUILDNAME = Pipes.re_expression(Consts.RE_GUILDNAME, 'guild.name', '公会名格式错误!')
    MOJANG_PROFILE = Pipes.api('mojang_profile', None, 'id', 'args.1')
    MOJANG_SESSION_NAME = Pipes.api('mojang_session', None, 'id', 'api_mojang_profile.id')
    MOJANG_SESSION_UUID = Pipes.api('mojang_session', None, 'id', 'args.1')
    MOJANG_SESSION_HYPIXEL_API = Pipes.api('mojang_session', None, 'id', 'api_hypixel_key.record.owner')
    MOJANG_SESSION_HYPIXEL_GUILDNAME = Pipes.api('mojang_session', None, 'id', 'guild.player.uuid')
    HYPIXEL_API = Pipes.api('hypixel_key', 'success', 'record', 'apiset.hypixel_apikey')
    HYPIXEL_PUNISHMENTSTATS = Pipes.api('hypixel_punishmentstats', 'success', 'staff_total', 'apiset.hypixel_apikey')
    HYPIXEL_PLAYER = Pipes.api('hypixel_player', 'success', 'player', 'apiset.hypixel_apikey', 'api_mojang_profile.id')
    HYPIXEL_GUILD_NAME = Pipes.api('hypixel_guild_name', 'success', 'guild', 'apiset.hypixel_apikey', 'guild.name')
    HYPIXEL_GUILD_PLAYER = Pipes.api('hypixel_guild_player', 'success', 'guild', 'apiset.hypixel_apikey', 'api_mojang_profile.id')
    ANTISNIPER_DENICK = Pipes.api('antisniper_denick', 'success', 'player.ign', 'apiset.antisniper_apikey', 'args.1')
    ANTISNIPER_FINDNICK = Pipes.api('antisniper_findnick', 'success', 'player.ign', 'apiset.antisniper_apikey', 'args.1')
    ANTISNIPER_WINSTREAK = Pipes.api('antisniper_winstreak', 'success', 'player.ign', 'apiset.antisniper_apikey', 'args.1')
    OPTIFINE_CAPE = Pipes.api_binary('optifine_cape', 'api_mojang_profile.name')
    OPTIFINE_BANNER = Pipes.api_binary('optifine_banner', 'ofcape.url', 'ofcape.valign')
    OPTIFINE_FORMAT = Pipes.api_optifine_format()
    QQAPI_QQAPI = Pipes.api('qqapi_qqapi', None, 'qq', 'args.1')
class Main:
    def __init__(self):
        self.record_messages = {}
        self.record_mode = None
        self.record_to = None
        self.recall_mode = None
        self.options = Options('yqloss_bot_options.txt', {
            'lists': {
                'global': {
                    'group_default': 'whitelist',
                    'group_whitelist': [],
                    'group_blacklist': [],
                    'user_default': 'whitelist',
                    'user_whitelist': [],
                    'user_blacklist': []
                },
                'disabled': {
                    'group_default': 'blacklist',
                    'group_whitelist': [],
                    'group_blacklist': [],
                    'user_default': 'blacklist',
                    'user_whitelist': [],
                    'user_blacklist': []
                },
                'admin': {
                    'group_default': 'blacklist',
                    'group_whitelist': [],
                    'group_blacklist': [],
                    'user_default': 'blacklist',
                    'user_whitelist': [],
                    'user_blacklist': []
                }
            },
            'bots': {
                'default': {
                    'lists': ['global']
                },
                'admin': {
                    'lists': ['admin']
                },
                'hypixelinternal': {
                    'lists': ['admin']
                },
                'qqapi': {
                    'lists': ['admin']
                }
            },
            'global': {
                'apisets': {
                    'default': {
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
                        'mojang_profile': 'https://api.mojang.com/users/profiles/minecraft/%s',
                        'mojang_session': 'https://sessionserver.mojang.com/session/minecraft/profile/%s',
                        'hypixel_apikey': '',
                        'hypixel_key': 'https://api.hypixel.net/key?key=%s',
                        'hypixel_player': 'https://api.hypixel.net/player?key=%s&uuid=%s',
                        'hypixel_status': 'https://api.hypixel.net/status?key=%s&uuid=%s',
                        'hypixel_guild_player': 'https://api.hypixel.net/guild?key=%s&player=%s',
                        'hypixel_guild_name': 'https://api.hypixel.net/guild?key=%s&name=%s',
                        'hypixel_friends': 'https://api.hypixel.net/friends?key=%s&uuid=%s',
                        'hypixel_recentgames': 'https://api.hypixel.net/recentgames?key=%s&uuid=%s',
                        'hypixel_punishmentstats': 'https://api.hypixel.net/punishmentstats?key=%s',
                        'hypixel_counts': 'https://api.hypixel.net/counts?key=%s',
                        'antisniper_apikey': '',
                        'antisniper_denick': 'https://api.antisniper.net/denick?key=%s&nick=%s',
                        'antisniper_findnick': 'https://api.antisniper.net/findnick?key=%s&name=%s',
                        'antisniper_winstreak': 'https://api.antisniper.net/winstreak?key=%s&name=%s',
                        'optifine_cape': 'http://s.optifine.net/capes/%s.png',
                        'optifine_banner': 'http://optifine.net/showBanner?format=%s&valign=%s',
                        'optifine_format': 'https://optifine.net/banners&&%s',
                        'qqapi_qqapi': 'https://zy.xywlapi.cc/qqapi?qq=%s'
                    }
                },
                'using_apiset': 'default',
                'reply_message': False,
                'cooldown_time': 1.0,
                'bypass_cooldown': [],
                'debug_mode': False,
                'prefixes': {
                    'default': '/'
                }
            },
            'options': {
                'admin': {
                    'commands': {}
                },
                'autoreply': {
                    'lower': False,
                    'strip': False,
                    'replies': {}
                },
                'luck': {
                    'default': [0, 100]
                },
                'hypixel': {
                    'ranks': {}
                }
            }
        })
        self.bot_map = {}
        self.register_bot(BotCommand('admin', ('',), (), lambda main, message: main.command(message.message[2:], message.group, message.user)[1]))
        self.register_bot(BotCommand('help', ('help', 'yhelp'), (Pipes.cooldown,), lambda main, message: '''
            Yqloss 机器人指令列表:
            %shelp|yhelp 显示指令列表
            %sluck|yluck 获取今日幸运值
            %smc|minecraft|profile|skin|mcskin <玩家> 查询玩家 Minecraft 信息
            %smcuuid|uuid <UUID> 查询 UUID 玩家信息
            %shyp|hypixel <玩家> [游戏] 查询 Hypixel 信息
            %sapi|key|apikey 查询当前使用的 API Key 信息
            %sban|bans|punishment|punishments 查询封禁信息
            %sbw|bedwar|bedwars <玩家> [模式] 查询起床战争数据
            %ssw|skywar|skywars <玩家> 查询空岛战争数据
            %smw|megawall|megawalls <玩家> 查询超级战墙数据
            %sduel|duels <玩家> [模式] 查询决斗游戏数据
            %sbsg|blitz <玩家> 查询闪电饥饿游戏数据
            %suhc <玩家> 查询 UHC 数据
            %smm|murder <玩家> 查询密室杀手数据
            %stnt|tntgame|tntgames <玩家> 查询掘战游戏数据
            %spit <玩家> 查询天坑之战数据
            %sgname|guildname <公会名称> 查询公会
            %sg|guild <玩家> 查询玩家所在公会
            %sbwshop|bwfav <玩家> 查询玩家起床战争商店
            %sdenick <Nick> 查询 Nick (Antisniper)
            %sfindnick <玩家> 查找 Nick (Antisniper)
            %sws|winstreak <玩家> 查询起床战争普通模式连胜 (Antisniper)
            %swsall|winstreakall <玩家> 查询起床战争其他模式连胜 (Antisniper)
            %swshyp <玩家> 查询起床战争普通模式连胜 (Hypixel)
            %swsallhyp <玩家> 查询起床战争其他模式连胜 (Hypixel)
            %sofcape|optifine <玩家> 查询 OptiFine 披风
        ''' % Utils.format(main, message, *(26 * ('prefix',)))))
        def current_time():
            time_ = time.localtime()
            return time_.tm_yday * 191981 + time_.tm_year * 1145
        self.register_bot(BotCommand('luck', ('luck', 'yluck'), (Pipes.cooldown,), lambda main, message: Utils.last(
            random.seed(message.user * 14 + current_time()),
            message.set('luck.from', main.options.get(f'options.luck.{message.user}', main.options.get(f'options.luck.default', [0, 100]))[0]),
            message.set('luck.to', main.options.get(f'options.luck.{message.user}', main.options.get(f'options.luck.default', [0, 100]))[1]),
            f'{message.at()}你今天的幸运值是 {random.randint(message.get("luck.from", 0), message.get("luck.to", 100))}%!'
        )))
        self.register_bot(BotAutoreply('autoreply'))
        message_profile = lambda main, message: '''
            名称: %s
            UUID: %s
            UU-ID: %s
            皮肤模型: %s
            皮肤: %s
            披风: %s
        ''' % Utils.format(main, message,
            'api_mojang_session.name?', 'api_mojang_session.id?',
            'session.id_dashed?', 'session.model?', 'session.skin?', 'session.cape?'
        )
        self.register_bot(BotCommand('mcname', ('mc', 'minecraft', 'profile', 'skin', 'mcskin'), (Pipes.cooldown, APIs.RE_USERNAME, APIs.MOJANG_PROFILE, APIs.MOJANG_SESSION_NAME, Pipes.session), message_profile))
        self.register_bot(BotCommand('mcuuid', ('mcuuid', 'uuid'), (Pipes.cooldown, APIs.RE_UUID, APIs.MOJANG_SESSION_UUID, Pipes.session), message_profile))
        self.register_bot(BotCommand('hypixelinternal', ('__hypixelinternal',), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.command_hypixel,
            Pipes.replace({'[': 'api_hypixel_player.player.', '(': 'api_hypixel_player.player.achievements.general_'})
        ), lambda main, message: '''
            %s 的 Hypixel 信息:
            等级: %s | 人品: %s%s
            成就点数: %s | 赠送 Rank: %s
            完成任务: %s | 完成挑战: %s
            小游戏胜场: %s | 获得硬币: %s
            活动银币: %s | 锦标赛战魂: %s
            使用语言: %s
            首次登录: %s
            上次登录: %s
            上次退出: %s
            最近游玩: %s%s
        ''' % Utils.format(main, message,
            'hypixel.name?', 'hypixel.level', '[karma', 'hypixel.rank_color?', '[achievementPoints', '[giftingMeta.ranksGiven',
            '(quest_master', '(challenger', '(wins', '(coins', '[seasonal.silver', '[tourney.total_tributes',
            '[userLanguage^?', '[firstLogin*?', '[lastLogin*?', '[lastLogout*?', '[mostRecentGameType^?', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('apikey', ('api', 'key', 'apikey'), (Pipes.cooldown,
            APIs.HYPIXEL_API, APIs.MOJANG_SESSION_HYPIXEL_API, Pipes.replace({'[': 'api_hypixel_key.record.', '(': 'api_mojang_session.'})
        ), lambda main, message: '''
            %s 的 API Key 信息:
            UUID: %s
            每分钟次数限制: %s
            一分钟内查询: %s
            总查询次数: %s
        ''' % Utils.format(main, message, '(name?', '[owner?', '[limit', '[queriesInPastMin', '[totalQueries')))
        self.register_bot(BotCommand('ban', ('ban', 'bans', 'punishment', 'punishments'), (Pipes.cooldown,
            APIs.HYPIXEL_PUNISHMENTSTATS, Pipes.replace({'[': 'api_hypixel_punishmentstats.'})
        ), lambda main, message: '''
            Hypixel 封禁信息:
            Watchdog 封禁:
            - 一分钟内: %s
            - 今日封禁: %s
            - 总封禁: %s
            Staff 封禁:
            - 今日封禁: %s
            - 总封禁: %s
        ''' % Utils.format(main, message, '[watchdog_lastMinute', '[watchdog_rollingDaily', '[watchdog_total', '[staff_rollingDaily', '[staff_total')))
        self.register_bot(BotCommand('bedwars', ('bw', 'bedwar', 'bedwars'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.command_bedwars, Pipes.game_mode(Maps.MODE_BEDWARS, 'bedwars.mode'),
            Pipes.replace({'[': 'api_hypixel_player.player.stats.Bedwars.', ']': '_bedwars', ')': '_resources_collected_bedwars'})
        ), lambda main, message: '''
            [%s%s] %s 的起床战争%s数据:
            经验: %s/%s | 硬币: %s | 连胜: %s
            拆床: %s | 被拆床: %s | BBLR: %s
            胜场: %s | 败场: %s | W/L: %s
            击杀: %s | 死亡: %s | K/D: %s
            终杀: %s | 终死: %s | FKDR: %s
            收集铁锭: %s | 收集金锭: %s
            收集钻石: %s | 收集绿宝石: %s%s
        ''' % Utils.format(main, message,
            'bedwars.level?', 'bedwars.star?', 'hypixel.name?', 'bedwars.mode?', 'bedwars.exp', 'bedwars.full_exp?',
            '[coins', '!winstreak?', '!beds_broken]', '!beds_lost]', '/', '!wins]', '!losses]', '/',
            '!kills]', '!deaths]', '/', '!final_kills]', '!final_deaths]', '/',
            '!iron)', '!gold)', '!diamond)', '!emerald)', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('skywars', ('sw', 'skywar', 'skywars'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.command_skywars, Pipes.replace({'[': 'api_hypixel_player.player.stats.SkyWars.'})
        ), lambda main, message: '''
            [%s%s] %s 的空岛战争数据:
            经验: %s/%s | 欧泊: %s | 碎片: %s/1.5k
            硬币: %s | 代币: %s
            时空漩涡: %s
            击杀: %s | 死亡: %s | K/D: %s
            胜场: %s | 败场: %s | W/L: %s
            灵魂: %s | 头颅: %s | 助攻: %s
            游戏时长: %s%s
        ''' % Utils.format(main, message,
            'skywars.level?', 'skywars.star?', 'hypixel.name?', 'skywars.exp', 'skywars.full_exp?','[opals', '[shard',
            '[coins', '[cosmetic_tokens', 'skywars.corrupt?', '[kills', '[deaths', '/',
            '[wins', '[losses', '/', '[souls', '[heads', '[assists', '[time_played&', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('megawalls', ('mw', 'megawall', 'megawalls'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.replace({'[': 'api_hypixel_player.player.stats.Walls3.'})
        ), lambda main, message: '''
            %s 的超级战墙数据:
            硬币: %s | 凋灵伤害: %s
            击杀: %s | 死亡: %s | K/D: %s
            终杀: %s | 终死: %s | FKDR: %s
            胜场: %s | 败场: %s | W/L: %s
            助攻: %s | 最终助攻: %s%s
        ''' % Utils.format(main, message,
            'hypixel.name?', '[coins', '[wither_damage', '[kills', '[deaths', '/', '[final_kills', '[final_deaths', '/',
            '[wins', '[losses', '/', '[assists', '[final_assists', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('duels', ('duel', 'duels'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.game_mode(Maps.MODE_DUELS, 'duels.mode'),
            Pipes.replace({'[': 'api_hypixel_player.player.stats.Duels.'})
        ), lambda main, message: '''
            %s 的决斗游戏%s数据:
            硬币: %s | 回合数: %s
            近战命中率: %s%% | 射击命中率: %s%%
            击杀: %s | 死亡: %s | K/D: %s
            胜场: %s | 败场: %s | W/L: %s%s
        ''' % Utils.format(main, message,
            'hypixel.name?', 'duels.mode?', '[coins', '!rounds_played', '?!melee_hits', '?!melee_swings', '%',
            '?!bow_hits', '?!bow_shots', '%', '`kills', '`deaths', '/', '!wins', '!losses', '/', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('blitz', ('bsg', 'blitz'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.plus(
                    'api_hypixel_player.player.stats.HungerGames.wins', 'api_hypixel_player.player.stats.HungerGames.deaths', 'blitz.games'
            ), Pipes.replace({'[': 'api_hypixel_player.player.stats.HungerGames.'})
        ), lambda main, message: '''
            %s 的闪电饥饿游戏数据:
            硬币: %s | 胜场: %s
            击杀: %s | 死亡: %s | K/D: %s
            游戏场数: %s | K/G: %s
            游戏时长: %s%s
        ''' % Utils.format(main, message,
            'hypixel.name?', '[coins', '[wins', '[kills', '[deaths', '/',
            '?[kills', 'blitz.games', '/', '[time_played&', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('uhc', ('uhc',), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.plus(
                'api_hypixel_player.player.stats.UHC.deaths', 'api_hypixel_player.player.stats.UHC.deaths_solo', 'uhc.deaths'
            ), Pipes.replace({'[': 'api_hypixel_player.player.stats.UHC.', '(': 'api_hypixel_player.player.achievements.uhc_'})
        ), lambda main, message: '''
            %s 的 UHC 数据:
            硬币: %s | 分数: %s
            击杀: %s | 死亡: %s | K/D: %s
            胜场: %s | 使用金头: %s%s
        ''' % Utils.format(main, message,
            'hypixel.name?', '[coins', '[score', '(hunter', 'uhc.deaths', '/',
            '(champion', '(consumer', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('mm', ('mm', 'murder'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.replace({'[': 'api_hypixel_player.player.stats.MurderMystery.'})
        ), lambda main, message: '''
            %s 的密室杀手数据:
            硬币: %s | 胜场: %s | 场数: %s
            击杀: %s | 死亡: %s | K/D: %s
            侦探概率: %s%% | 杀手概率: %s%%
            弓箭击杀: %s | 飞刀击杀: %s%s
        ''' % Utils.format(main, message,
            'hypixel.name?', '[coins', '[wins', '[games', '[kills', '[deaths', '/',
            '[detective_chance', '[murderer_chance', '[bow_kills', '[knife_kills', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('tnt', ('tnt', 'tntgame', 'tntgames'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.replace({'[': 'api_hypixel_player.player.stats.TNTGames.'})
        ), lambda main, message: '''
            %s 的掘战游戏数据:
            硬币: %s
            方块掘战: 纪录: %s | 胜场: %s
            PvP 方块掘战: 纪录: %s | 胜场: %s
            - 击杀: %s | 死亡: %s | K/D: %s
            烫手 TNT: 胜场: %s
            - 击杀: %s | 死亡: %s | K/D: %s
            掘一死箭: 胜场: %s | 死亡: %s
            法师掘战: 胜场: %s | 助攻: %s
            - 击杀: %s | 死亡: %s | K/D: %s%s
        ''' % Utils.format(main, message,
            'hypixel.name?', '[coins', '[record_tntrun&?', '[wins_tntrun', '[record_pvprun&?', '[wins_pvprun',
            '[kills_pvprun', '[deaths_pvprun', '/', '[wins_tntag', '[kills_tntag', '[deaths_tntag', '/',
            '[wins_bowspleef', '[deaths_bowspleef', '[wins_capture', '[assists_capture',
            '[kills_capture', '[deaths_capture', '/', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('pit', ('pit',), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.plus(
                'api_hypixel_player.player.stats.Pit.pit_stats_ptl.kills', 'api_hypixel_player.player.stats.Pit.pit_stats_ptl.assists', 'pit.kill_and_assist'
            ), Pipes.replace({'[': 'api_hypixel_player.player.stats.Pit.pit_stats_ptl.', '(': 'api_hypixel_player.player.stats.Pit.profile.'})
        ), lambda main, message: '''
            %s 的天坑之战数据:
            金币: %s | 最高连杀: %s
            击杀: %s | 死亡: %s | K/D: %s
            助攻: %s | K+A/D: %s%s
        ''' % Utils.format(main, message,
            'hypixel.name?', '(cash', '[max_streak', '[kills', '[deaths', '/',
            '[assists', '?pit.kill_and_assist', '?[deaths', '/', 'hypixel.name_change?'
        )))
        message_guild = lambda main, message: '''
            公会名称: %s
            等级: %s (%s/%s)
            创建时间: %s
            人数: %s | 标签: %s
            标签颜色: %s
            双倍经验: %s%% | 双倍硬币: %s%%
            是否公开: %s
            主打游戏: %s
        ''' % Utils.format(main, message,
            '[name?', 'guild.level', 'guild.exp', 'guild.full_exp?', '[created*?', 'guild.member_count',
            '[tag?', 'guild.tag_color?', 'guild.double_exp', 'guild.double_coins', '[publiclyListed$', 'guild.preferred_games?'
        )
        self.register_bot(BotCommand('guildname', ('gname', 'guildname'), (Pipes.cooldown,
            lambda main, message: message.set('guild.name', ' '.join(message.args[1:])), APIs.RE_GUILDNAME,
            APIs.HYPIXEL_GUILD_NAME, Pipes.command_guild('name'), Pipes.command_guild_player('name'), APIs.MOJANG_SESSION_HYPIXEL_GUILDNAME,
            Pipes.replace({'[': 'api_hypixel_guild_name.guild.'})
        ), lambda main, message: message_guild(main, message) + '''
            会长: %s | 完成挑战: %s
            加入时间: %s
            近 7 天经验: %s %s %s %s %s %s %s
        ''' % Utils.format(main, message,
            'api_mojang_session.name?', 'guild.player.questParticipation', 'guild.player.joined*?',
            'guild.player.exp.0', 'guild.player.exp.1', 'guild.player.exp.2', 'guild.player.exp.3',
            'guild.player.exp.4', 'guild.player.exp.5', 'guild.player.exp.6'
        )))
        self.register_bot(BotCommand('guild', ('g', 'guild'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_GUILD_PLAYER, Pipes.command_guild('player'), Pipes.command_guild_player('player'),
            Pipes.replace({'[': 'api_hypixel_guild_player.guild.'})
        ), lambda main, message: ('''
            %s 的公会信息:
            权限组: %s | 完成挑战: %s
            加入时间: %s
            近 7 天经验: %s %s %s %s %s %s %s
        ''' % Utils.format(main, message,
            'api_mojang_profile.name?', 'guild.player.rank?', 'guild.player.questParticipation', 'guild.player.joined*?',
            'guild.player.exp.0', 'guild.player.exp.1', 'guild.player.exp.2', 'guild.player.exp.3',
            'guild.player.exp.4', 'guild.player.exp.5', 'guild.player.exp.6'
        )) + message_guild(main, message)))
        self.register_bot(BotCommand('bwshop', ('bwshop', 'bwfav'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.hypixel, Pipes.command_bedwars
        ), lambda main, message: '''
            [%s%s] %s 的起床战争商店:
            快速购买:%s
            物品栏:%s%s
        ''' % Utils.format(main, message,
            'bedwars.level?', 'bedwars.star?', 'hypixel.name?', 'bedwars.shop?', 'bedwars.slots?', 'hypixel.name_change?'
        )))
        self.register_bot(BotCommand('denick', ('denick',), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.ANTISNIPER_DENICK, Pipes.replace({'[': 'api_antisniper_denick.player.'})
        ), lambda main, message: '''
            %s -> %s
            查询的 Nick: %s
            Denick 时间: %s
            上次发现: %s
            (数据来自 Antisniper)
        ''' % Utils.format(main, message, '[ign?', '[latest_nick?', '[queried_nick?', '[first_detected~?', '[last_seen~?')))
        self.register_bot(BotCommand('findnick', ('findnick',), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.ANTISNIPER_FINDNICK, Pipes.replace({'[': 'api_antisniper_findnick.player.'})
        ), lambda main, message: '''
            %s -> %s
            Denick 时间: %s
            上次发现: %s
            (数据来自 Antisniper)
        ''' % Utils.format(main, message, '[ign?', '[nick?', '[first_detected~?', '[last_seen~?')))
        self.register_bot(BotCommand('winstreak', ('ws', 'winstreak'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.ANTISNIPER_WINSTREAK, Pipes.replace({'(': 'api_antisniper_winstreak.player.', '[': 'api_antisniper_winstreak.player.data.', ']': '_winstreak'})
        ), lambda main, message: '''
            %s 的起床战争连胜数据:
            总连胜: %s
            单人模式: %s
            双人模式: %s
            3v3v3v3: %s
            4v4v4v4: %s
            (4v4: %s)
            (数据来自 Antisniper)
        ''' % Utils.format(main, message, '(ign?', '[overall]?', '[eight_one]?', '[eight_two]?', '[four_three]?', '[four_four]?', '[two_four]?')))
        self.register_bot(BotCommand('winstreakall', ('wsall', 'winstreakall'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.ANTISNIPER_WINSTREAK, Pipes.replace({
                '(': 'api_antisniper_winstreak.player.',
                '[': 'api_antisniper_winstreak.player.data.eight_two_',
                '<': 'api_antisniper_winstreak.player.data.four_four_',
                ']': '_winstreak'
        })), lambda main, message: '''
            %s 的起床战争连胜数据:
            (总连胜: %s)
            4v4: %s
            40v40 城池攻防战: %s
            双人疾速模式: %s
            4v4v4v4 疾速模式: %s
            双人超能力模式: %s
            4v4v4v4 超能力模式: %s
            双人枪战模式: %s
            4v4v4v4 枪战模式: %s
            双人幸运方块模式: %s
            4v4v4v4 幸运方块模式: %s
            双人无虚空模式: %s
            4v4v4v4 无虚空模式: %s
            双人 Underworld 模式: %s
            4v4v4v4 Underworld 模式: %s
            双人交换模式: %s
            4v4v4v4 交换模式: %s
            (数据来自 Antisniper)
        ''' % Utils.format(main, message,
            '(ign?', '(data.overall]?', '(data.two_four]?', '(data.castle]?', '[rush]?', '<rush]?',
            '[ultimate]?', '<ultimate]?', '[armed]?', '<armed]?', '[lucky]?', '<lucky]?',
            '[voidless]?', '<voidless]?', '[underworld]?', '<underworld]?', '[swap]?', '<swap]?'
        )))
        self.register_bot(BotCommand('winstreakhypixel', ('wshyp', ), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.replace({
                '(': 'api_hypixel_player.player.',
                '[': 'api_hypixel_player.player.stats.Bedwars.',
                ']': '_winstreak'
        })), lambda main, message: '''
            %s 的起床战争连胜数据:
            总连胜: %s
            单人模式: %s
            双人模式: %s
            3v3v3v3: %s
            4v4v4v4: %s
            (4v4: %s)
            (数据来自 Hypixel)
        ''' % Utils.format(main, message, '(displayname?', '[winstreak?', '[eight_one]?', '[eight_two]?', '[four_three]?', '[four_four]?', '[two_four]?')))
        self.register_bot(BotCommand('winstreakallhypixel', ('wsallhyp',), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.HYPIXEL_PLAYER, Pipes.replace({
                '(': 'api_hypixel_player.player.',
                ':': 'api_hypixel_player.player.stats.Bedwars.',
                '[': 'api_hypixel_player.player.stats.Bedwars.eight_two_',
                '<': 'api_hypixel_player.player.stats.Bedwars.four_four_',
                ']': '_winstreak'
        })), lambda main, message: '''
            %s 的起床战争连胜数据:
            (总连胜: %s)
            4v4: %s
            40v40 城池攻防战: %s
            双人疾速模式: %s
            4v4v4v4 疾速模式: %s
            双人超能力模式: %s
            4v4v4v4 超能力模式: %s
            双人枪战模式: %s
            4v4v4v4 枪战模式: %s
            双人幸运方块模式: %s
            4v4v4v4 幸运方块模式: %s
            双人无虚空模式: %s
            4v4v4v4 无虚空模式: %s
            双人 Underworld 模式: %s
            4v4v4v4 Underworld 模式: %s
            双人交换模式: %s
            4v4v4v4 交换模式: %s
            (数据来自 Hypixel)
        ''' % Utils.format(main, message,
            '(displayname?', ':winstreak?', ':two_four]?', ':castle]?', '[rush]?', '<rush]?',
            '[ultimate]?', '<ultimate]?', '[armed]?', '<armed]?', '[lucky]?', '<lucky]?',
            '[voidless]?', '<voidless]?', '[underworld]?', '<underworld]?', '[swap]?', '<swap]?'
        )))
        def pipe_command(commands):
            def _(main, message):
                message.data['commands'] = commands
            return _
        def command_bot(name):
            commands = {}
            bot = self.get_bot(name)
            for command in bot.commands:
                commands[command] = bot
            return commands
        self.register_bot(BotCommand('hypixel', ('hyp', 'hypixel'), (APIs.RE_USERNAME,
            pipe_command({
                **command_bot('hypixelinternal'),
                **command_bot('bedwars'),
                **command_bot('skywars'),
                **command_bot('megawalls'),
                **command_bot('duels'),
                **command_bot('blitz'),
                **command_bot('uhc'),
                **command_bot('mm'),
                **command_bot('tnt'),
                **command_bot('pit'),
                **command_bot('guild'),
                **command_bot('bwshop'),
                **command_bot('denick'),
                **command_bot('findnick'),
                **command_bot('winstreak'),
                **command_bot('winstreakall'),
                **command_bot('winstreakhypixel'),
                **command_bot('winstreakallhypixel'),
            }),
        ), lambda main, message:
            message.get(f'commands.{message.get("args.2", "__hypixelinternal")}', BotError(BotException('未知的指令!'))).process(main, Message(main,
                group=message.group, user=message.user, id=message.id, raw_message=
                    f'{Consts.PREFIX}{message.get("args.2", "__hypixelinternal")} {message.get("args.1", "?")} ' +
                    ' '.join(message.args[3:])
            ))
        ))
        self.register_bot(BotCommand('optifinecape', ('ofcape', 'optifine'), (Pipes.cooldown, APIs.RE_USERNAME,
            APIs.MOJANG_PROFILE, APIs.OPTIFINE_CAPE, APIs.OPTIFINE_FORMAT, Pipes.command_optifine_cape,
        ), lambda main, message: '''
            %s 的 OptiFine 披风信息:
            Design: %s%s
            Top: %s
            Bottom: %s%s
        ''' % Utils.format(main, message,
            'api_mojang_profile.name?', 'ofcape.design?', 'ofcape.banner?', 'ofcape.top?', 'ofcape.bottom?', 'ofcape.custom?'
        )))
        self.register_bot(BotCommand('qqapi', ('qqapi',), (Pipes.cooldown, APIs.RE_QQNUMBER, APIs.QQAPI_QQAPI), lambda main, message: '''
            %s 的 QQ 账号信息:
            手机号: %s
            地区: %s
        ''' % Utils.format(main, message, 'api_qqapi_qqapi.qq?', 'api_qqapi_qqapi.phone?', 'api_qqapi_qqapi.phonediqu?')))
    def register_bot(self, bot):
        self.bot_map[bot.name] = bot
        if self.options.get(f'bots.{bot.name}') is None:
            self.options.set(f'bots.{bot.name}', Utils.copy(self.options.get('bots.default')))
    def get_bot(self, name):
        return self.bot_map[name]
    def get_bots(self):
        return self.bot_map
    def process(self, message):
        try:
            if isinstance(self.record_mode, tuple) and self.record_mode == (message.group, message.user) and self.record_to is not None:
                self.record_messages[self.record_to] = message.message
                self.record_mode = None
                self.record_to = None
                message.send(self, 'Record Success!')
            elif isinstance(self.recall_mode, tuple) and self.recall_mode == (message.group, message.user):
                if message.message.startswith('[CQ:reply,id='):
                    message_id = message.message[13:]
                    message_id = message_id[:message_id.find(']')]
                    message_id = int(message_id)
                    Utils.recall_message(message_id)
                self.recall_mode = None
            else:
                for bot_name, bot in self.bot_map.items():
                    if bot.can_process(self, message):
                        if bot.have_permission(self, message):
                            bot.process(self, message)
                        break
        except Exception as e:
            if self.options.get('global.debug_mode', False):
                message.send(self, message.at() + traceback.format_exc())
            else:
                message.send(self, message.at() + str(e))
    @Utils.escape_bracket
    def command(self, command_line, group, user):
        try:
            command_line = command_line.replace('&#91;', '[')
            command_line = command_line.replace('&#93;', ']')
            command, *args_ = command_line.split()
            args = []
            for arg in args_:
                for name, record in self.record_messages.items():
                    arg = arg.replace(f'{{record_{name}}}', record)
                args.append(arg)
            if command == 'quit':
                self.options.write_options()
                return True, 'Quitting...'
            elif command == 'keys':
                return False, tuple(self.options.get(eval(args[0])).keys())
            elif command == 'get':
                return False, self.options.get(eval(args[0]))
            elif command == 'set':
                self.options.set(eval(args[0]), eval(args[1]) if len(args) >= 2 else self.record_messages[''])
                self.options.write_options()
                return False, 'Set Success!'
            elif command == 'append':
                lst = self.options.get(eval(args[0]))
                value = eval(args[1]) if len(args) >= 2 else self.record_messages['']
                duplicate = value in lst
                lst.append(value)
                self.options.write_options()
                return False, 'Append Success!' + (' (Duplicate)' if duplicate else '')
            elif command == 'remove':
                lst = self.options.get(eval(args[0]))
                value = eval(args[1]) if len(args) >= 2 else self.record_messages['']
                in_list = value in lst
                lst.remove(value)
                self.options.write_options()
                return False, 'Remove Success!' + ('' if in_list else ' (Not in List)')
            elif command == 'record':
                self.record_to = args[0] if len(args) >= 1 else ''
                self.record_mode = (group, user)
                return False, 'Recording...'
            elif command == 'getrecord':
                return False, self.record_messages[args[0] if len(args) >= 1 else '']
            elif command == 'getrecords':
                return False, self.record_messages
            elif command == 'clearrecords':
                self.record_messages = {}
                return False, 'Clear Record Success!'
            elif command == 'getprefix':
                return False, Consts.PREFIX
            elif command == 'recall':
                self.recall_mode = (group, user)
                return False, ''
            elif command == 'cmd':
                cmd = self.options.get(f'options.admin.commands.{args[0]}', 'Love Q_TT')
                for i, arg in enumerate(args):
                    cmd = cmd.replace(f'{{arg_{i}}}', arg)
                return self.command(cmd, group, user)
            elif command == 'reset':
                location = eval(args[0])
                self.options.set(location, Utils.get(self.options.default_options, location))
                return False, 'Reset Success!'
            elif command == 'setfrom':
                self.options.set(eval(args[0]), self.options.get(eval(args[1]) if len(args) >= 2 else self.record_messages['']))
                return False, 'SetFrom Success!'
            else:
                return False, 'Unknown Command.'
        except Exception:
            return False, traceback.format_exc()
    def console_loop(self):
        while True:
            try:
                command = input('>>> ')
                do_exit, output = self.command(command, -2, -1)
                print(output)
                if do_exit:
                    break
            except Exception:
                traceback.print_exc()
    def main(self):
        Utils.start_listener(self)
        self.console_loop()
if __name__ == '__main__':
    Main().main()

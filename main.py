import base64
import socket
import ssl
import sys
from getpass import getpass


class Imap:
    def __init__(self, server, port, mail_addr, mailbox, start, end, ssl_available: bool):
        self.server = server
        self.port = port
        self.mail_addr = mail_addr
        self.mailbox = mailbox
        self.start = start
        self.end = end
        if ssl_available:
            low_sock = socket.create_connection((self.server, self.port))
            context = ssl.create_default_context()
            self.sock = context.wrap_socket(low_sock, server_hostname=self.server)
        self.increment = 0

    def start_work(self):
        self.login()
        self.select_mailbox()


    def select_mailbox(self):
        self.send_command(f"aaa{self.increment} SELECT {self.mailbox}")
        self.receive_answer()

    def login(self):
        password = getpass(prompt='Введите пароль от почты: ')
        self.send_command(f'aaa{self.increment} LOGIN {self.mail_addr} {password}')
        self.receive_answer()

    def send_command(self, command):
        self.increment += 1
        self.sock.send((command + '\r\n').encode('utf-8'))

    def receive_answer(self):
        response = b''
        while True:
            try:
                string = self.sock.recv(1024)
                response += string
                if len(string) < 1024:
                    break
            except Exception:
                break
        message = response.decode('utf-8')
        if 'BAD' in message or 'NO' in message:
            raise Exception("server error message")
        while not any([x in message for x in ['BAD', 'NO', 'OK']]):
            message += self.receive_answer()
        return message

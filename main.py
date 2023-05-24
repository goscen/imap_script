import base64
import quopri
import re
import socket
import ssl
import sys
from argparse import ArgumentParser
from getpass import getpass


class Imap:
    def __init__(self, server, port, mail_addr, start, end, ssl_available: bool):
        self.server = server
        self.port = port
        self.mail_addr = mail_addr
        self.start = int(start)
        self.end = int(end)
        if ssl_available:
            try:
                low_sock = socket.create_connection((self.server, self.port))
                context = ssl.create_default_context()
                self.sock = context.wrap_socket(low_sock, server_hostname=self.server)
            except:
                print("Bad port")
                sys.exit()
        else:
            self.sock = socket.create_connection((self.server, self.port))
        self.increment = 0

    def start_work(self):
        self.login()
        self.select_mailbox()
        self.read_letters()

    def select_mailbox(self):
        self.send_command(f"aaa{self.increment} LIST * *")
        boxes = self.receive_answer()
        print(boxes)
        box = input("Введите название ящика: ")
        self.send_command(f"aaa{self.increment} SELECT {box}")
        try:
            self.receive_answer()
        except:
            print("box not exist")
            sys.exit()

    def login(self):
        password = getpass()
        try:
            self.send_command(f'aaa{self.increment} LOGIN {self.mail_addr} {password}')
            self.receive_answer()
            self.receive_answer()
        except Exception:
            print("Password not correct/Server needs ssl")
            sys.exit()

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
        message = response.decode('utf-8', errors="ignore")
        if 'BAD' in message or 'NO' in message:
            raise Exception()
        while not any([x in message for x in ['BAD', 'NO', 'OK']]):
            message += self.receive_answer()
        return message

    def read_letters(self):
        # try:
        self.send_command(f"aaa{self.increment} SEARCH ALL")
        answer = self.receive_answer()
        number_of_letters = re.findall(r"\d+", answer)
        number_of_letters = int(number_of_letters[-2])
        need_to_read = self.end - self.start + 1
        if int(number_of_letters) < need_to_read:
            print(f"To many letter\nYou need: {need_to_read}\nMails in box: {number_of_letters}")
            sys.exit()
        elif int(number_of_letters) < self.end:
            print(f"Big id of letter\nYou need: {self.end}\nMails in box: {number_of_letters}")
            sys.exit()

        if self.end == 0:
            self.end = number_of_letters

        for i in range(self.start, self.end + 1):
            # извлекаем заголовки
            self.send_command(
                f"aaaa{self.increment} FETCH {i} (BODY[HEADER.FIELDS (FROM TO SUBJECT DATE)])"
            )
            try:
                answer = self.receive_answer()
            except:
                continue
            headers = self.parse_header(answer)
            self.send_command(f"aaaa{self.increment} FETCH {i} RFC822.SIZE")
            answer = self.receive_answer()
            size = re.findall("RFC822\.SIZE \d+", answer)
            headers.append(size[0][12:])
            # извлекаем вложения
            self.send_command(
                f"aaaa{self.increment} FETCH {i} BODYSTRUCTURE"
            )
            answer = self.receive_answer()
            files = self.parse_body(answer)
            self.print_info(headers, files)

    # except Exception as e:
    #     print(e)
    #     print("error on server")
    #     sys.exit()

    def print_info(self, headers, files):
        print()
        headers_info = ["От", "Кому", "Тема", "Дата и время", "Размер письма"]
        headers_bad_info = ["From", "To", "Subject", "Date", "-"]
        files_info = ["Вложения", "Имя", "Размер"]
        for i in range(len(headers)):
            if headers_bad_info[i] in headers[i]:
                print(f"{headers_info[i]}: {headers[i][len(headers_bad_info[i])+1:]}")
            else:
                print(f"{headers_info[i]}: {headers[i]}")
        print()
        if files[0] == 0:
            print("No attachments")
        else:
            for i in range(len(files)):
                print(f"{files_info[i]}: {files[i]}")

    def parse_header(self, data):
        print(data)
        mail_from = re.findall(r"From:.+\r\n", data)
        mail_to = re.findall(r"To:.+\r\n", data)
        subject = re.findall(r"Subject:.+\r\n", data)
        date = re.findall(r"Date:.+\r\n", data)
        if not mail_from:
            mail_from = ["Not given"]
        if not mail_to:
            mail_to = ["Not given"]
        if not subject:
            subject = ["Not given"]
        if not date:
            date = ["Not given"]
        data_to_decode = [mail_from[0], mail_to[0], subject[0], date[0]]
        headers = []
        for data in data_to_decode:
            header = self.decode_string(data)
            headers.append(header)
        return headers

    def parse_body(self, data):
        number_of_attachments = len(re.findall(r'\("attachment" \(', data))
        file_names = re.findall(r'\("name" [^)]+', data)
        for i in range(len(file_names)):
            file_names[i] = self.decode_string(file_names[i][8:])
        file_size = re.findall(r'\d{2,} NIL', data)
        for i in range(len(file_size)):
            file_size[i] = file_size[i][0:file_size[i].find("NIL") - 1]
        return number_of_attachments, file_names, file_size

    def decode_string(self, data: str):
        if "?=" in data:
            encoding = ""
            start_index = data.find("=?")
            for i in data[start_index + 2:]:
                if i != "?":
                    encoding += i
                else:
                    break
            end_index = data.rfind("?=")
            decoding = re.findall("\?.", data)[1][1]
            decoded_data = ""
            try:
                if decoding == "B":
                    decoded_data = base64.b64decode(data[start_index + 10:end_index]).decode(encoding, errors="ignore")
                elif decoding == "Q":
                    decoded_data = quopri.decodestring(data[start_index + 10:end_index]).decode(encoding, errors="ignore")
            except:
                decoded_data = ""
            data = data[end_index + 3:len(data)]
            return f"{decoded_data} {data}"
        return data


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--ssl", dest="use_ssl", action="store_true", required=False,
                        help="Использовать ssl")
    parser.add_argument("-s", "--server", dest="server", required=True,
                        help="imap сервер и порт,server:port, если порт не указан, то по дефолту порт = 143")
    parser.add_argument("-n", dest="mails", required=False, nargs="+", default=[1],
                        help="С какого по какое письмо читать, по дефолту все")
    parser.add_argument("-u", "--user", dest="user", required=True, type=str, help="Mail клиента")

    args = parser.parse_args()
    server_name = args.server.split(":")
    if len(server_name) == 1:
        server = server_name[0]
        port = 143
    else:
        server = server_name[0]
        port = server_name[1]

    if len(args.mails) == 1:
        begin = args.mails[0]
        end = 0
    else:
        begin = args.mails[0]
        end = args.mails[1]
    script = Imap(server,
                  port,
                  args.user,
                  begin,
                  end,
                  args.use_ssl
                  )
    script.start_work()

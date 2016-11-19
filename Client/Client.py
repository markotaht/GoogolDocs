from socket import AF_INET, SOCK_STREAM, socket, SHUT_RD
from socket import error as soc_err
from threading import Thread, Lock
from Queue import Queue
import ClientUI
from Commons import *
import time
import Tkinter

from Server.Server import Server

import logging
FORMAT='%(asctime)s (%(threadName)-2s) %(message)s'
logging.basicConfig(level=logging.INFO,format=FORMAT)

class Client():

    def __init__(self):
        self.lock = Lock()
        self.file = ""
        self.socket = None
        self.server = None
        self.queue = Queue()
        self.queue.put((self._synchronise,[]))
        self.textField = None
        self.createUI()
        #TESTIB Tahe saatmist ja eemaldamist.
    #    self.connect(('192.168.56.1',7777))
   #     self.sendLetter("a",0)
    #    print self.removeLetter(0)

    def connect(self,srv_addr,name,password):
        self.socket = socket(AF_INET, SOCK_STREAM)
        try:
            self.socket.connect(srv_addr)
            logging.info('Connected to ConcurrentEditing server at %s:%d' % srv_addr)
            if self.sendIntroduction(name,password) == RSP_INTRODUCTION_NOTOK:
                self.socket.close()
                return False
            self.loop()

            return True
        except soc_err as e:
            logging.error('Can not connect to the server at %s:%d' \
                          ' %s ' % (srv_addr + (str(e),)))
        return False

    def sendIntroduction(self,name,password):
        data = name + ":" + password
        data =serialize(data)
        req = INTRODUCTION+MSG_FIELD_SEP+data
        return self.send(req)

    def requestModification(self):
        req = REQ_MODIFICATION + MSG_FIELD_SEP
        rsp = self.send(req)
        return rsp.split(":")

    def processLocalChange(self, textField, oldVersion, newVersion, changeType, changeIndex, changeChar):
        print(oldVersion + " -> " + newVersion)
        print(changeType + "" + changeChar + " at " + str(changeIndex))

        if changeType == "+":
            self.sendLetter(changeChar, changeIndex)
        elif changeType == "-":
            self.removeLetter(changeIndex)


    def sendLetter(self, letter, index):
        logging.info("Sending letter: " + letter + " index " + str(index))
        args = [letter,index]
        self.queue.put((self._sendLetter, args))

    def _sendLetter(self,args):
        code,ID = self.requestModification()
        if code == RSP_MODIFICATION_NOTOK:
            return
        data = ID + ":" + str(args[1]) + ":" +args[0]
        data = serialize(data)
        req = REQ_SEND_LETTER + MSG_FIELD_SEP + data
        logging.info("\"Add letter\" change with changeID " + ID + " sent.")
        return self.send(req)

    def removeLetter(self, index):
        logging.info("Remove letter from index: " + str(index))
        args = [index]
        self.queue.put((self._removeLetter, args))

    def _removeLetter(self,args):
        code, ID = self.requestModification()
        if code == RSP_MODIFICATION_NOTOK:
            return
        data = serialize(ID +":"+str(args[0]))
        req = REQ_REMOVE_LETTER + MSG_FIELD_SEP + data
        return self.send(req)

    def _synchronise(self,args):

        #Synchronization
        req = REQ_SYNCHRONIZE + MSG_FIELD_SEP
        data = self.send(req)
        content = deserialize(data[3:])

        #print(content)

        if(self.textField != None):
            try:
                self.textField.delete(0,Tkinter.END)
            except:
                pass
            self.textField.insert(0,content)


        self.queue.put((self._synchronise, []))
        #logging.info("Server has" + content)
        return

    def addColaborator(self,name,password):
        self.server.file.addCollaborator(name,password)

    def openLocally(self):
        #run server
        self.server = Server()
        self.server.start()
        time.sleep(0.01)
        self.connect(("127.0.0.1", 7777),"me","admin")
        logging.info("Connected to server.")

    def send(self,msg):
        m = msg + MSG_SEP
        with self.lock:
            r = False
            try:
                self.socket.sendall(m)
                r = self._receive()
            except KeyboardInterrupt:
                self.socket.close()
                logging.info('Ctrl + C issued, terminating...')
            except soc_err as e:
                if e.errno == 107:
                    logging.warn('Server closed connection, terminating ...')
                else:
                    logging.error('Connection error: %s' % str(e))
                self.socket.close()
                logging.info('Disconnected')
            return r

    def _receive(self):
        message, bits = '', ''
        try:
            bits = self.socket.recv(DEFAULT_RCV_BUFSIZE)
            message += bits
            while len(bits) > 0 and not (bits.endswith(MSG_SEP)):
                bits = self.socket.recv(DEFAULT_RCV_BUFSIZE)
                message += bits
            if len(bits) <= 0:
                self.socket.close()
                message = ''
            message = message[:-1]
        except KeyboardInterrupt:
            self.socket.close()
            message = ''
            return 0
        except soc_err as e:
            if e.errno == 107:
            #    logging.warn('Client %s:%d left before server could handle it' \
            #             '' % self.client_addr)
                message = ""
            else:
                logging.error('Error: %s' % str(e))
            self.socket.close()
            message = ''
            return 0
        return message

    def close(self):
        if not self.socket == None:
            self.socket.shutdown(SHUT_RD)
            self.socket.close()
            self.socket = None
        self.queue.put(None)

    def createUI(self):
        self.ui = ClientUI.ClientUI(self)
        self.ui.start();

    def loop(self):
        sendThread = Thread(target=self._sendLoop, args=(self,))
        sendThread.setName("CLIENT-SEND-LOOP")
        sendThread.start()

        return

    def _sendLoop(self, parent):
        logging.info("Starting client sender loop...")
        while 1:
            while not parent.queue.empty():
                event = parent.queue.get()
                try:
                    if event == None:
                        break
                    event[0](event[1])
                except soc_err:
                    break

            time.sleep(0.001)

if __name__ == '__main__':
    c = Client()
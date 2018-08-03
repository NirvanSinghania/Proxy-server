import os
import socket
import sys
import datetime
import time
import json
import base64
import copy
import thread
import email.utils as eut
import re
import threading

# global variables
proxy_port = 12345
BUFFER_SIZE = 4096
MAX_CACHE_BUFFER = 3
CACHE_DIR = "./cache"


class LockSystem:
    def __init__(self):
        self.__mutex={}

    # For locking file given by filepath
    def grant_lock(self,filepath):
        try:
            if not filepath in self.__mutex:
                self.__mutex[filepath] = threading.Lock()
            (self.__mutex[filepath]).acquire()
        except:
            print "Error in granting lock"
            sys.exit()

    # For unlocking file given by filepath
    def take_lock_away(self,filepath):
        try:
            if filepath in self.__mutex:
                self.__mutex[filepath].release()
            else:
                print "Invalid filepath"
        except:
            sys.exit()




class proxy_server:
    def __init__(self):
        self.NO_OF_OCC_FOR_CACHE = 2
        self.MIN_OCC_IN_LOGS_FOR_CACHE = 2
        self.__logs = {}
        self.max_connections = 10
        self.lock = LockSystem()

    def edit_logs(self,filepath, c_addr): # for editing the logs

        filepath = filepath.replace("/", "__")
        if not filepath in self.__logs: # if no entry is present for filepath in logs
            self.__logs[filepath] = [] # then initialising for that entry
        date_time = time.strptime(time.ctime(), "%a %b %d %H:%M:%S %Y") # Retrieving date and time of recent modification
        self.__logs[filepath].append({"datetime" : date_time, "client" : json.dumps(c_addr),})

    def cache_eligiblity(self,filepath):

        log_file_name = filepath.replace("/", "__")
        log_occ = len(self.__logs[log_file_name])

        # if no. of times this file is requested >= min_occ_ then return true
        return log_occ >= self.MIN_OCC_IN_LOGS_FOR_CACHE
        

    def acquire_cache_info(self,filepath):
        # To acquire the previous cache information

        filepath = CACHE_DIR + "/" + (filepath.lstrip('/')).replace("/", "__")
        if not os.path.isfile(filepath):
            last_mtime = None # if no previous info then last modification time is null
        else:
            last_mtime = time.strptime(time.ctime(os.path.getmtime(filepath)), "%a %b %d %H:%M:%S %Y")
        return filepath, last_mtime

    def create_cache(self):
        # for creating cache directory if not already present
        if os.path.isdir(CACHE_DIR): pass
        else: os.makedirs(CACHE_DIR)

        # for deleting previous(of prev. session) cached file from the ./cache folder
        for file in os.listdir(CACHE_DIR):
            file_path = CACHE_DIR + "/" + file
            os.remove(file_path)

    def dataParser(self,c_data):
  
        inp = c_data.splitlines()
        #clean data for empty entries
        inp = [ x for x in inp if x!='']
        
        #url with ip port and file name
        url_data = inp[0].split()
        url = url_data[1]
        method = url_data[0]

        #regex match to extract data out of url
        matchobj = re.match(r'(.*)://(.*):(.*)/(.*)', url,re.M)
        
        if matchobj:
            server_url = matchobj.group(2)
            server_port = int(matchobj.group(3))
            url_data[1] = "/"+ matchobj.group(4)
        

        protocol = "http"
        #setting the first argument with filename
        inp[0] = ' '.join(url_data)

        #final data to be sent to server
        final_data = "\r\n".join(inp) + '\r\n\r\n'

        #create the dictionary
        L = [server_port,server_url,url,final_data,protocol,method ]
        keys = [ "server_port", "server_url", "total_url","c_data", "protocol","method"]
        return dict(zip(keys,L))

    # insert the header
    def insert_if_modified(self,details):

        inp = details["c_data"].splitlines()
        
        inp = [ x for x in inp if x!='']

        # for making the header. will be used for checking whether the file is modified or not
        hdr = time.strftime("%a %b %d %H:%M:%S %Y", details["last_mtime"])
        msg = "If-Modified-Since: "
        hdr = msg + hdr
        inp.append(hdr)

        details["c_data"] = "\r\n".join(inp)
        details["c_data"] = details["c_data"] + "\r\n\r\n"
        return details


    # serve get request
    def cacheDetailHandler(self,c_addr, details):

        self.lock.grant_lock(details["total_url"])

        self.edit_logs(details["total_url"], c_addr)

        # for updating values do_cache, cache_path and last_mtime
        details["do_cache"] = self.cache_eligiblity(details["total_url"])
        details["cache_path"], details["last_mtime"] = self.acquire_cache_info(details["total_url"])

        self.lock.take_lock_away(details["total_url"])

        return details


    # if cache is full then delete the least recently used cache item
    def cacheSpaceHandler(self, filepath):
        cache_files = os.listdir(CACHE_DIR)
        if len(cache_files) < MAX_CACHE_BUFFER:
            return
        for file in cache_files:
            self.lock.grant_lock(file)
        last_mtime = min(self.__logs[file][-1]["datetime"] for file in cache_files)

        # To removes the least recently asked cached response
        file_to_del = [file for file in cache_files if self.__logs[file][-1]["datetime"] == last_mtime]
        os.remove(CACHE_DIR + "/" + file_to_del)

        for file in cache_files:
            self.lock.take_lock_away(file)

    def Controller(self,c_conn, c_addr, details):
        last_mtime = details["last_mtime"]
        cache_path = details["cache_path"]
        server_url = details["server_url"]
        server_port = details["server_port"]
        total_url = details["total_url"]
        iscachereqd = details["do_cache"]
        c_data = details["c_data"]

        s_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_conn.connect((server_url, server_port))
        s_conn.send(c_data)

        resp = s_conn.recv(BUFFER_SIZE) #server response

        if last_mtime and "304 Not Modified" in resp:
            # if file is present in ./cache folder and it is not modified
            print "returning cached file from %s to %s" % (cache_path, str(c_addr))
            self.lock.grant_lock(total_url)
            f = open(cache_path, 'rb')
            block = f.read(BUFFER_SIZE)
            while block:
                c_conn.send(block)  # for sending responde to the client
                block = f.read(BUFFER_SIZE)
            f.close()
            self.lock.take_lock_away(total_url)

        elif iscachereqd:
            # if satisfies the cache eligibility i.e iscachreqd is True
            print "caching file while serving %s to %s" % (cache_path, str(c_addr))
            self.cacheSpaceHandler(total_url)
            self.lock.grant_lock(total_url)
            f = open(cache_path, "w+")
            while len(resp):
                c_conn.send(resp) # for sending responde to the client
                f.write(resp) # for writing in the cache file
                resp = s_conn.recv(BUFFER_SIZE) 
            f.close()
            self.lock.take_lock_away(total_url)
            c_conn.send("\r\n\r\n")

        else:
            # if not eligible for cache and is not already present or modified version in cache 
            print "without caching serving %s to %s" % (cache_path, str(c_addr))
            while len(resp):
                c_conn.send(resp)  # for sending responde to the client
                resp = s_conn.recv(BUFFER_SIZE)
            c_conn.send("\r\n\r\n")

        # closing all the sockets
        s_conn.close()
        c_conn.close()

        return

# A thread function to handle one request
    def requestHandler(self,c_conn, c_addr, c_data):

        details = self.dataParser(c_data)
        if not details:
            print "no any details"
            c_conn.close()
            return

        details = self.cacheDetailHandler(c_addr, details)
        if details["last_mtime"]:
            details = self.insert_if_modified(details)
        self.Controller(c_conn, c_addr, details)

        c_conn.close()
        print c_addr, "closed"

    # This funciton initializes socket and starts listening.
    # When connection request is made, a new thread is created to serve the request
    def start(self):

        # Initialize socket
        self.create_cache()
        try:
            # initializing socket
            proxy_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            proxy_conn.bind(('127.0.0.1', proxy_port))
            proxy_conn.listen(self.max_connections)

            proxy_server = proxy_conn.getsockname()[0]

            msg = "Serving proxy on " + proxy_server + " port " + str(proxy_port) + " ..." 
            print msg

        except Exception:
            proxy_conn.close()
            err_msg = "Error in starting proxy server ..." 
            print err_msg
            raise SystemExit

        while True:
            try:
                c_conn, c_addr = proxy_conn.accept()
                c_data = c_conn.recv(BUFFER_SIZE)

                # print c_data
                print
                # message for error handling purpose
                msg = str(c_addr) + ' - '
                msg = msg + "[" + str(datetime.datetime.now()) + "] "
                msg = msg + "\"" + c_data.splitlines()[0] + "\""  
                print msg

                # start a new thread for the request
                thread.start_new_thread(
                    self.requestHandler,
                    (
                        c_conn,
                        c_addr,
                        c_data
                    )
                )

            # if any keyboard interruption occurs then close all sockets
            except KeyboardInterrupt:
                msg = "\nProxy server shutting down ..."
                print msg
                c_conn.close()
                proxy_conn.close()
                break


proxy = proxy_server()
proxy.start()




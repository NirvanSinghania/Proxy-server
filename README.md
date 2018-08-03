# Proxy Server
An HTTP proxy server implemented via python socket programming with caching, threading

## Description
- proxy.py is the main proxy file
- server.py is the main server file
- The proxy server will forward the client’s request to the web server. The web server 
  will then generate a response message and deliver it to the proxy server, which in 
  turn sends it to the client 
- Only GET requests are handled

## Features
- Receives the request from client and pass it to the server after necessary parsing
- Threaded proxy server thus able to handle many requests at the same time
- To maintain integrity, cached files are accessed by securing mutex locks
- Cache has limited size, so if the cache is full and proxy wants to store another response then it removes the least recently asked cached response. Cache limit can be set by setting up the constant MAX_CACHE_BUFFER
- File is added to the cache when file is at least requested for the 2nd time because 
  adding it the first time will overload the server and there is no guarantee that the 
  object will be requested again.
- code has error handling and comments 

## How to run

### Proxy
- python proxy.py
- It will run proxy on port 12345

### Server
- Hosted at localhost/20000 or 127.0.0.1/20000
- To run: python server.py

### Client

- Using browser: 

  - Set proxy on your browser

  - Now all the proxy requests will pass through the proxy server including ones from 

    already started webpages.
    
  - Type the full path i.e. localhost:20000/filename.txt to get the file 

- Using curl commands

  - curl -x http://localhost:12345 http://127.0.0.1:20000/filename.txt

## Assignment Details
- Language used
  - Python 2.7

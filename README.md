# cpp-pvpjudge
## About 
A judge server to run epic PvP coding matches! 
## Overview
Step 1: Give it a **judge.cpp** file. 

Step 2: Give two players' source code (must also be .cpp files for now; we promise there will be support for Python files soon). 

Step 3: Wait 5 seconds, and you can get the match result back!
## How to run the server 
Step 1: Pull the image _hoanggiapvuvhg/cpp-pvp-judge_ from Dockerhub. On Ubuntu: 
```
sudo docker pull hoanggiapvuvhg/cpp-pvp-judge
```
Step 2: Run the server: 
```
sudo docker run -p ${whatever-port-you-want}:9000 hoanggiapvuvhg/cpp-pvp-judge
```
Step 3: Send a POST request with the files!
Sample request with postman: 

<img width="840" alt="Screen Shot 2023-09-24 at 2 29 46 am" src="https://github.com/CodecupHSGS/cpp-pvpjudge/assets/112223883/039d0252-0ae6-48af-a591-b5d56019d4fa">

You will get a submission ID from the response: 

<img width="477" alt="Screen Shot 2023-09-24 at 2 32 28 am" src="https://github.com/CodecupHSGS/cpp-pvpjudge/assets/112223883/67bf6311-4a17-4229-a04c-7902f809faff">

Step 4: Profit!!
Get on the browser and enter 
```
http://127.0.0.1:${whatever-port-you-want}/log/{submission-ID}
http://127.0.0.1:${whatever-port-you-want}/results/{submission-ID}
```
<img width="509" alt="Screen Shot 2023-09-24 at 2 36 24 am" src="https://github.com/CodecupHSGS/cpp-pvpjudge/assets/112223883/732e2a2c-d75f-4945-a30d-297b66124929">

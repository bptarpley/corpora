# Corpora

This is a barebones readme that needs a lot of work :) Right now it just has quick instructions for running your own instance locally using Docker:

1. Install Docker (i.e. for [Mac](https://docs.docker.com/docker-for-mac/install/)
2. Create a Corpora base directory, i.e. /Users/username/corpora
3. Create the following subdirectories inside that base directory:
..* corpora (this will contain all user-uploaded and task-generated files)
..* archive (this contains the MongoDB database files)
..* link (this contains the Neo4J database files)
..* search (this contains the ElasticSearch index files)
..* static (this contains the Django web application's static files)
4. Clone this repository somewhere other than your corpora basedir: `git clone -b dev ssh://git@gitlab.dh.tamu.edu:10022/bptarpley/corpora.git`
5. Copy the file "docker-compose.yml.example" and save a copy as "docker-compose.yml" in the same directory
6. Replace all instances of "/your/corpora/basedir" with the path to your basedir, i.e. /Users/username/corpora
7. Fire it up! To do so, open a terminal window and change to the directory where you saved your "docker-compose.yml" file. Then, execute one of these commands:
..* `docker-compose up` (This will bring up the docker containers and will spit out all logs to your terminal window. When you hit ctrl+c, you'll stop all running containers)
..* `docker-compose up -d` (This will bring up the containers but will not spit out logs. To stop the containers, you'll need to run `docker-compose stop`)
..* `docker-compose up -d && docker-compose logs -f corpora` (This will bring up all containers and only show logs for the Django web application. Hitting ctrl+c will only stop the logs.)

Note that when Corpora fires up for the first time, it will create a default user according to the environment variables specified in docker-compose.yml for the "corpora" service. By default, that user's credentials are "corpora" (both username and password).
# Managing

There are a few tasks, such as managing users, backing up and restoring corpus data, and installing plugins that Corpora admins may need to perform.

## Managing Users

To manage the users (or Scholars) on your instance of Corpora, click the blue "Manage Scholars" button in the footer of the table listing corpora on the homepage of the web application.

Once on the "Scholars" page, you should see a table listing all the users in your instance of Corpora. You may click on the column names to sort, you can use the search box, or page through this list in order to find your user. Once you've found them, click on their username which should also be an orange link. This will bring up the "Manage Scholar" modal.

### Granting/Revoking Admin Privileges

Admins in Corpora are able to create a new corpus, view and edit all data for existing corpora, run all corpus notebooks, and run all tasks. You can make a user an admin for your instance of Corpora by clicking the orange "Grant Admin Privileges" button. Once a user is an admin, that same button will read "Revoke Admin Privileges."

### Granting/Revoking Corpus Permissions

In order for a user to edit content, run a corpus notebook, or run certain tasks, they must either be an Admin for the instance of Corpora or be granted "Editor" privileges on a specific corpus. To do the latter, expand the "Corpus permissions" tray. In the "New Permission" form, provide the name of the corpus, choose "Editor" from the dropdown menu, and click "Set Permission." To revoke that privilege, find it under "Existing Permissions" and choose "None" from the dropdown.

### Granting/Revoking Job Permissions

While admins can run all jobs, users with Editor permissions on a corpus must be explicitly granted permission to run specific jobs. To do so, expand out the user's "Job permissions" tray. You can either check the box next to the specific task they need to be able to run, or check the "Local (HUEY)" box, which grants them privileges to run every local task. Once you've checked the appropriate box(es), click the orange "Set Permissions" button. Job permissions can be revoked by unchecking boxes and clicking "Set Permissions" again.

### Changing Passwords

When logged in, individual users can change their passwords by clicking on the orange "My Account" button on the top right of a page in Corpora. Should they need their passwords reset, however, you may do so by pulling up their "Manage Scholar" modal and expanding the "Change password" tray. You may then provide their new password, confirm it, and click the "Change Password" button.

## Backing Up and Restoring Corpus Data

When logged in as user with admin privileges, you should see several buttons on the footer of the table that lists all of the corpora on the home page of your instance of Corpora. To back up or restore corpus data, click the blue "Corpus Backups" button to manage corpus backups.

### Backing Up

Corpus data can be backed up as a "gzipped tar file," which includes metadata about your corpus, any files uploaded to your corpus or content types, and MongoDB database dumps of all the content in your corpus. To create an backup file, select the relevant corpus from the "Corpus" dropdown, provide a name (a default name is optionally provided for you), and click the orange "Create" button. Depending on how large your corpus is, this can take some time. Once an backup has been created, however, it should show up under "Existing Backups" beneath the creation form upon refreshing the page. Multiple backups for the same corpus may be created--they must, however, have unique names.

In order to restore a corpus or migrate it to another instance of Corpora, you may download the file by clicking on its orange link in the "Backup File" column of the Existing Backups table. It is strongly recommended that you do *not* rename this file after you download it.

### Restoring

To restore a corpus backup, it must be listed in the "Existing Backups" table. If it's not listed there, scroll to the bottom of the page where it says "Import a Backup File." You may simply drag and drop your downloaded backup file into the gray box to make it available.* Once your backup file appears in the "Existing Backups" table, you may click the blue "Restore" button to the right of it to commence the restore process. Note that the restore process maintains the original unique ID assigned to your corpus at the time of creation. As such, if you already have a version of that corpus on your instance of Corpora, you must first delete it before performing a restore. To delete an existing corpus you must be logged in as an admin user. You can then go to that corpus' home page, click on the "Admin" tab, scroll to the bottom, and use the corpus deletion form.

Depending on the amount of data in your corpus, restoring can take a long time, as data is being restored to MongoDB, Elasticsearch, and Neo4J.

**Note:* Certain very large corpus backup files (usually over 3GB in size) may cause the upload process to timeout, preventing you from registering it as an available corpus to restore. If this happens, you will have to register it manually. To do so, navigate to the data directory of your instance of Corpora as it exists on the machine/server hosting your instance, i.e. `/corpora/data`. Inside that directory will be several subdirectories such as "archive," "link," "search," etc. Go inside the subdirectory named "corpora" and find the directory named backups, i.e. `/corpora/data/corpora/backups`. Copy your large export file into this directory. You'll then have to execute a Django management command on the machine hosting Corpora by performing the following steps:

1. Open a terminal or command prompt.
2. Determine the name of the container running Corpora. You can do that by running the command `docker ps`. This will output information about all the containers running on your machine. In the "NAMES" column of this output, you'll want to find the container name for Corpora, which will either be something like `corpora-corpora-1` if you're using Docker Compose, or `corpora_corpora.1.[alphanumeric id]` if you're using Docker Swarm. Make note of this container name.
3. Execute the following command in your terminal:
````bash
docker exec -it [container name] python3 manage.py register_backup_file [backup filename]
````

Note that when providing the backup filename in the command above, you only need the name of the file (not the full path). Once that command executes and you get a message saying "Backup file successfully registered," you should be able to see it listed as an available corpus backup to restore on the "Corpus Backups" page. 

## Installing Plugins

Corpora is designed with a plugin architecture that leverages Django's "app" convention. As such, installing plugins for Corpora is relatively easy, though you must have access to the filesystem of the server. A given plugin is ultimately a directory with a particular file structure (see [creating plugins for Corpora](/corpora/developing/#building-corpora-plugins)). To install a plugin, place its directory inside the "plugins" subdirectory living in the data directory for Corpora, i.e. `/corpora/data/plugins`. Once the plugin directory is copied there, you must also enable the plugin by adding it to the comma delimited list of enabled plugins stored in the `CRP_INSTALLED_PLUGINS` environment variable set for the Corpora container. The easiest way to do this is to edit the `docker-compose.yml` file, find the "environment" section of the "corpora" service, make sure the line specifying `CRP_INSTALLED_PLUGINS` isn't commented out, and add the name of the plugin directory to that variables' comma delimited value.


*Corpora must be restarted* for it to be registered properly. And in order for containers to be aware of updated environment variables, the container must be stopped altogether and re-created by the Docker engine. To completely stop and restart Corpora while running with Docker Compose, issue these commands:

````bash
# first change to your codebase directory with the docker-compose.yml file
docker-compose down
# wait 20 seconds or so for the containers to stop
docker-compose up -d
````

To completely stop and restart Corpora while running as a Swarm service, issue these commands:

````bash
# first change to your codebase directory with the docker-compose.yml file
docker stack rm corpora
# wait 20 seconds or so for the containers to stop
docker stack deploy corpora -c docker-compose.yml
````

## Scaling Corpora

Should your instance of Corpora receive high traffic volume, it is architected in such a way as to support multiple instances of the Corpora container--this is due to the fact that they all rely on the Redis container for session management. Scaling in this way has only been tested with a [Docker Swarm deployment](/corpora/deploying/#running-in-swarm-mode), and may be accomplished by setting the `scale` key in the service configuration for Corpora in `docker-compose.yml`, or by issuing [the appropriate Docker command](https://docs.docker.com/engine/swarm/swarm-tutorial/scale-service/). Scaling Corpora in this way will also multiply the number of Huey task workers you're able to run concurrently. You could alternatively scale Huey by increasing the number of Huey workers in a given Corpora container by setting the `CRP_HUEY_WORKERS` environment variable to something higher than the default, which is currently `10`.
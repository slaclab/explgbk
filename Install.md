For the logbook, we will create a Mongo database per experiment.
First create some users in mongo with read and read/write permissions for all databases.
We'll be using these accounts from the service.
```
use admin
db.createUser(
  {
    user: "admin",
    pwd: "somepassword",
    roles: [ { role: "userAdminAnyDatabase", db: "admin" }, { role: "root", db: "admin" } ]
  }
)
db.createUser(
 {
    user: "reader",
    pwd: "somepassword",
    roles: [ { role: "readAnyDatabase", db: "admin" } ]
 }
)

db.createUser(
 {
    user: "writer",
    pwd: "somepassword",
    roles: [ { role: "readWriteAnyDatabase", db: "admin" } ]
 }
)
```
We have a special `site` database that has all the information that spans experiments.
We'll need some special collections+data in this database.
Precreate a couple of the collections with the appropriate indices.
```
use site
db['roles'].create_index( [("app", ASCENDING), ("name", ASCENDING)], unique=True)
db['experiment_switch'].create_index( [("experiment_name", ASCENDING), ("instrument", ASCENDING),  ("station", ASCENDING), ("switch_time", ASCENDING)])

```

Add a few roles to let you login to the log book for all experiments.
```
use site
db['roles'].insertMany([
{
	"app" : "LogBook",
	"name" : "Editor",
	"privileges" : [
		"read",
		"post",
		"edit",
		"delete"
	],
	"players" : [
		"uid:editor"    
	]
},
{
	"app" : "LogBook",
	"name" : "Writer",
	"privileges" : [
		"post",
		"read"
	],
	"players" : [
		"group_containing_all_writers",
    "uid:writer"    
	]
},
{
	"app" : "LogBook",
	"name" : "Reader",
	"privileges" : [
		"read"
	],
	"players" : [
		"group_containing_all_readers",
    "uid:reader"    
	]
}
])

```

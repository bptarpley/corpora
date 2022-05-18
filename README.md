# Corpora

This is a barebones readme that needs a lot of work :) Right now it just has quick instructions for running your own instance locally using Docker, and brief documentation for the content API.

## Installation

1. Install Docker (i.e. for [Mac](https://docs.docker.com/docker-for-mac/install/))
2. Create a Corpora base directory, i.e. /Users/username/corpora
3. Create the following subdirectories inside that base directory:
   * corpora (this will contain all user-uploaded and task-generated files)
   * archive (this contains the MongoDB database files)
   * link (this contains the Neo4J database files)
   * search (this contains the ElasticSearch index files)
   * conf (this contains the Django auth database)
   * static (this contains the Django web application's static files)
4. Clone this repository somewhere other than your corpora basedir: `git clone -b dev http://gitlab.dh.tamu.edu/bptarpley/corpora.git`
5. Copy the file "docker-compose.yml.example" and save a copy as "docker-compose.yml" in the same directory
6. Replace all instances of "/your/corpora/basedir" with the path to your basedir, i.e. /Users/username/corpora
7. Fire it up! To do so, open a terminal window and change to the directory where you saved your "docker-compose.yml" file. Then, execute one of these commands:
   * `docker-compose up` (This will bring up the docker containers and will spit out all logs to your terminal window. When you hit ctrl+c, you'll stop all running containers)
   * `docker-compose up -d` (This will bring up the containers but will not spit out logs. To stop the containers, you'll need to run `docker-compose stop`)
   * `docker-compose up -d && docker-compose logs -f corpora` (This will bring up all containers and only show logs for the Django web application. Hitting ctrl+c will only stop the logs.)

Note that when Corpora fires up for the first time, it will create a default user according to the environment variables specified in docker-compose.yml for the "corpora" service. By default, that user's credentials are "corpora" (both username and password). Once it finishes the setup process, you can access Corpora's web interface at http://localhost

## Content API

Once content types have been created within a corpus' "Content Type Manager," and once instances of content exist for a given content type, that
content type has its own API allowing third-party apps to query for content hosted within Corpora. There are two endpoints for any given
content type--the "List" and "Detail" endpoints.

If upon creating your corpus you chose the "Open Access" option, there is no authentication needed to access either of these endpoints. If you chose
not to make your corpus open access, however, two things must be true before you can access these endpoints:

1. You must provide the authentication token of a Corpora user within a header for each request. The header's name must be "Authentication" and the value for that header must be "Token [ the authentication token ]"
2. You must be querying the endpoint from a valid IP address specified in the user profile associated with that authentication token. To add/manage valid IP addresses, simply login to Corpora and click the "My Account" button on the upper-right. 

### The List Endpoint

Content can be listed or queried for en-masse via the List endpoint, which can be accessed at the following URL:

`https://[ your.corpora.domain ]/api/corpus/[ corpus ID ]/[ content type name ]/`

Your corpus ID can be determined by visiting your corpus' main page. For instance, if you created a corpus called "My Corpus,"
you would click on your corpus' name ("My Corpus") on the main landing page at https://[ your.corpora.domain ]. Once you're on your corpus' main page,
you'll note that the URL looks something like this:

`https://[ your.corpora.domain ]/corpus/5f60bf2cc879ea00329af449/`

Your corpus' ID is located between the last two slashes of the URL (in the above example, the ID for the corpus is 5f60bf2cc879ea00329af449).

The content type name is the name you provided for your content type when you created it in the Content Type Manager for your corpus. At present,
all corpuses come with the "Document" content type by default. To access the List API for the Document content type in the example corpus above, for example, you'd use this endpoint:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Document/`

This endpoint accepts several different GET parameters (passed via the query string):

| Parameter | Purpose | Example
| --------- | ------- | -------
| `q` | To perform a general query against all keyword and text fields for your content | [endpoint url]?q=search
| `q_[field name]` | To perform a full-text query against a specific field | [endpoint url]?q_title=Ulysses
| `f_[field name]` | To filter by an exact value for a specific field | [endpoint url]?f_color=green
| `w_[field name]` | To perform wildcard matching on a specific field (note: if no asterix is found in the search term, one will be automatically appended at the end) | [endpoint url]?w_name=Br*
| `r_[field name]` | To filter using a range of possible values (numeric fields only). Separate min and max values by two underscores (if either min or max are omitted, range will just be "less than or equal to" or "greater than or equal to" respectively). | [endpoint url]?r_size=6__10
| `s_[field name]` | To sort results by field name, settings value to either "ASC" or "DESC" | [endpoint_url]?s_pub_date=DESC
| `page-size` | To specify the size of each page of results | [endpoint_url]?page-size=50
| `page` | To specify which page of results you'd like | [endpoint_url]?page=1
| `page-token` | After 9,000 records worth of pages, you'll receive a "page token" in the JSON response which will need to be captured and specified in order to retrieve further pages. | [endpoint_url]?page-token=5f60bf2cc879ea00329af449
| `operator` | To specify which logical operator is used to combine queries (default "and") | [endpoint_url]?q_color=red&q_holiday=Christmas&operator=or

Parameters can of course be chained together. If you wanted, for instance, to see the first 50 Documents with "Ulysses" in the title
sorted by publication date in descending order, you could query the endpoint like this:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Document/?q_title=Ulysses&s_pub_date=DESC&page-size=50&page=1`

You may perform queries using multiple search terms on the same field, though this is _not_ acheived by chaining the same GET parameter together. In order to do this, you must separate the multiple values with two underscores (__) as your delimiter. So, to search a hypothetical field named "color" for both "red" and "green" values, do this:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Clothing/?q_color=red__green`

By default, however, the "and" operator is used to combine queries, so you'll likely also want to add `operator=or` so that results that are either "red" or "green" are returned:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Clothing/?q_color=red__green&operator=or`

Results are returned in JSON format, with two main (upper-level) keys: "meta," and "records." The "meta" key is a hash with the following key/value pairs:

* **content_type**: The name of the content type being queried, i.e. "Document"
* **has_next_page**: A boolean specifying whether more pages of results exist, i.e. true
* **num_pages**: The total number of pages available given the specified page size, i.e. 122
* **page**: The current page of results, i.e. 1
* **page_size**: The size of each page of results, i.e. 50
* **total**: The total number of documents matching query parameters, i.e. 6,097

The "records" key refers to a list of actual results (the content being queried for). Each item in the list is a hash representing the content, with the keys being field names and the values being the values stored in those fields.
**NOTE**: Aside from the mandatory "id," "label," and "uri" fields, only fields for which the "In Lists?" flag has been set to true in the Content Type Manager appear here.

### The Detail Endpoint

Whereas the List endpoint provides a way to query for content and see values for fields marked as being "In Lists," the detail endpoint allows you to
see the values for _every_ field for a given, individual piece of content. To access the endpoint for an individual piece of content, use this URL:

`https://[ your.corpora.domain ]/api/corpus/[ corpus ID ]/[ content type name ]/[ content ID ]/`

So, for instance, assuming you're interested in all the data for a Document with the
ID "5f734833741449002ba9907e," you could access that data at the following URL:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Document/5f734833741449002ba9907e/`

Results are returned in JSON format, as a hash where keys are field names and values are the data stored in those fields.
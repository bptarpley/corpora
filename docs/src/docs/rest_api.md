# The Content REST API

One of Corpora's affordances is a dynamically generated REST API for your corpus. At this time, the API is read-only.

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

#### List Endpoint Parameters

This endpoint accepts several different GET parameters (passed via the query string):

| Parameter                        | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Example
|----------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| -------
| `q`                              | To perform a general query against all keyword and text fields for your content                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | [endpoint url]?q=search
| `q_[field name]`                 | To perform a full-text query against a specific field                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | [endpoint url]?q_title=Ulysses
| `f_[field name]`                 | To filter by an exact value for a specific field                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | [endpoint url]?f_color=green
| `w_[field name]`                 | To perform wildcard matching on a specific field (note: if no asterix is found in the search term, one will be automatically appended at the end)                                                                                                                                                                                                                                                                                                                                                                                                    | [endpoint url]?w_name=Br*
| `e_[field name]`                 | To specify only results that have a value (not empty) for a specific field (note: the value for this parameter is irrelevant)                                                                                                                                                                                                                                                                                                                                                                                                                        | [endpoint url]?e_author=y
| `r_[field name]`                 | To filter using a range of possible values (for number, decimal, date, and geospatial fields). Separate min and max values by "to" (for number, decimal, and date fields, if either min or max are omitted, range will just be "less than or equal to" or "greater than or equal to" respectively). When parsing dates for range queries, Corpora makes use of the [dateutil package for Python](https://dateutil.readthedocs.io/en/stable/examples.html#parse-examples) so that dates can be specified in a variety of ways.                        | Number/Decimal:<br />[endpoint url]?r_size=6to10<br /><br />Date:<br />[endpoint url]?r_size=1/1/1980to12/31/1989<br /><br />Geospatial (bounding box):<br />[endpoint url]?r_location=[lon],[lat]to[lon],[lat] 
| `s_[field name]`                 | To sort results by field name, settings value to either "ASC" or "DESC". NOTE: geospatial and large text fields cannot be sorted.                                                                                                                                                                                                                                                                                                                                                                                                                    | [endpoint_url]?s_pub_date=DESC
| `a_terms_[aggregation_name]`     | To produce a list of unique values for a field and their corresponding counts (appears in the "meta" section of results). Any alphanumeric string may be used for [aggregation_name].                                                                                                                                                                                                                                                                                                                                                                | [endpoint_url]?a_terms_uniquecolors=color
| `a_min_[aggregation_name]`       | To determine the min value for a field (appears in the "meta" section of results). Any alphanumeric string may be used for [aggregation_name].                                                                                                                                                                                                                                                                                                                                                                                                       | [endpoint_url]?a_min_lowestage=age
| `a_max_[aggregation_name]`       | To determine the max value for a field (appears in the "meta" section of results). Any alphanumeric string may be used for [aggregation_name].                                                                                                                                                                                                                                                                                                                                                                                                       | [endpoint_url]?a_max_highestage=age
| `a_histogram_[aggregation_name]` | To produce a histogram of values at a given interval for a field (appears in the "meta" section of results). Any alphanumeric string may be used for [aggregation_name]. The value for this parameter must be a field name, two underscores, and then the desired interval.                                                                                                                                                                                                                                                                          | [endpoint_url]?a_histogram_decades=age__10
| `a_geobounds_[aggregation_name]` | To produce a bounding box (top left and bottom right lat/long coordinates) for all the values in a geo_point field (appears in the "meta" section of results). Any alphanumeric string may be used for [aggregation_name]. The value for this parameter must be a valid geo_point field name.                                                                                                                                                                                                                                                        | [endpoint_url]?a_geobounds_region=coordinates
| `a_geotile_[aggregation_name]`   | To produce a series of "geotiles" and the corresponding number of values found within each tile for a given geo_point field (appears in the "meta" section of results). Any alphanumeric string may be used for [aggregation_name]. The value for this parameter must be a field name, two underscores, and then the desired precision for the geotile. Read more about geotile aggregation and the precision value [here](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-geotilegrid-aggregation.html). | [endpoint_url]?a_geotile_areas=coordinates__9
| `page-size`                      | To specify the size of each page of results                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | [endpoint_url]?page-size=50
| `page`                           | To specify which page of results you'd like                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | [endpoint_url]?page=1
| `page-token`                     | After 9,000 records worth of pages, you'll receive a "page token" in the JSON response which will need to be captured and specified in order to retrieve further pages.                                                                                                                                                                                                                                                                                                                                                                              | [endpoint_url]?page-token=5f60bf2cc879ea00329af449
| `operator`                       | To specify which logical operator is used to combine queries (default "and")                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | [endpoint_url]?q_color=red&q_holiday=Christmas&operator=or

#### Chaining Parameters

Parameters can of course be chained together. If you wanted, for instance, to see the first 50 Documents with "Ulysses" in the title
sorted by publication date in descending order, you could query the endpoint like this:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Document/?q_title=Ulysses&s_pub_date=DESC&page-size=50&page=1`

You may perform queries using multiple search terms on the same field, though this is _not_ acheived by chaining the same GET parameter together. In order to do this, you must separate the multiple values with two underscores (__) as your delimiter. So, to search a hypothetical field named "color" for both "red" and "green" values, do this:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Clothing/?q_color=red__green`

By default, however, the "and" operator is used to combine queries, so the above query would only make sense in a scenario where the `color` field is multi-valued. If you want to change the operator used to combine queries, you can do so by using the `operator` parameter like so:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Clothing/?q_color=red__green&operator=or`

This would provide results where the hypothetical `color` field contains the values `red` _or_ `green`. **Note**: when changing the operator in this manner, you're changing how _all_ queries are combined. Consider this scenario:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Clothing/?q_color=red__green&q_texture=smooth&operator=or`

Because the operator is changed to `or`, and unfortunate side effect occurs: results are returned where the value of `color` is either `red` or `green` _or_ the value of the hypothetical `texture` field is `smooth`. In other words, you could have results where the value of `texture` is `smooth` but the value of `color` is `brown`!

In order to construct queries with more complicated, nested boolean logic, you may make use of numerical prefixes that group queries together. If, for instance, you wanted results where, effectively (texture=smooth AND (color=red OR color=green)), you could create the following query:

`https://[ your.corpora.domain ]/api/corpus/5f60bf2cc879ea00329af449/Clothing/?q_texture=smooth&1_q_color=red__green&1_operator=or`

The prefix of `1_` before the `q_color` and `operator` parameters place them in a nested group together. That nested group is then combined with the `q_texture` query using the default `and` operator. The Corpora list API supports up to 9 different groups to create complicated nested queries, making use of numerical prefixes `1_` through `9_`.

#### Endpoint Output

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

### The Last Updated Endpoint

This goal of this endpoint is to provide a timestamp indicating the last time any content of this type was modified. This is useful for when content 
is being cached somewhere and the client needs to know if the data is now stale. To access this endpoint, use the following URL pattern:

`https://[ your.corpora.domain ]/api/corpus/[ corpus ID ]/[ content type name ]/last-updated/`

Results are returned in JSON with a single key (`last_updated`) with the value being either zero (no content) or a timestamp in the form of an integer.

### The Network JSON Endpoint

The Network JSON Endpoint is useful for creating graph visualizations on the fly using tools like the [viz.js Network package for JavaScript](https://visjs.github.io/vis-network/docs/network/) used by Corpora's UI. You can access this endpoint using the following URL pattern:

`https://[ your.corpora.domain ]/api/corpus/[ corpus ID ]/[ content type name ]/[ content ID ]/network-json/`

This endpoint queries the Neo4J graph database for the relationships surrounding a single piece of content and returns the results as nodes and edges. That single piece of content can be considered the focal node, and it's specified via the URL parameters in the endpoint URL.

According to the logic of this endpoint, the focal node can have various "relationship types." These relationships consist of other pieces of content associated with the focal node via cross reference relationships. Let's assume, for instance, that you have a simple content type called `Book` with the fields `author` and `printer`, each of which are cross references to the `Person` content type. In that case, 
a single focal node of the type `Book` could have two relationship types, described as `hasauthor` and `hasarinter`.

Here is an example response based on the simple dataset described above:

```JSON
{
    "nodes": [
        {
            "id": "/corpus/68f79a692f2c5bbb2ccc600a/Book/69c419f71e0f29727c369573",
            "group": "Book",
            "label": "NW"
        },
        {
            "id": "/corpus/68f79a692f2c5bbb2ccc600a/Person/69c419f31e0f29727c369572",
            "group": "Person",
            "label": "Penguin"
        },
        {
            "id": "/corpus/68f79a692f2c5bbb2ccc600a/Person/69c419e71e0f29727c369571",
            "group": "Person",
            "label": "Zadie Smith"
        }
    ],
    "edges": [
        {
            "id": "1580615",
            "title": "hasprinter",
            "from": "/corpus/68f79a692f2c5bbb2ccc600a/Book/69c419f71e0f29727c369573",
            "to": "/corpus/68f79a692f2c5bbb2ccc600a/Person/69c419f31e0f29727c369572"
        },
        {
            "id": "1580614",
            "title": "hasauthor",
            "from": "/corpus/68f79a692f2c5bbb2ccc600a/Book/69c419f71e0f29727c369573",
            "to": "/corpus/68f79a692f2c5bbb2ccc600a/Person/69c419e71e0f29727c369571"
        }
    ],
    "meta": {
        "hasprinter-Person": {
            "count": 1,
            "skip": 0,
            "limit": 20,
            "collapsed": false
        },
        "hasauthor-Person": {
            "count": 1,
            "skip": 0,
            "limit": 20,
            "collapsed": false
        }
    }
}
```

Note the `meta` part of the response above. It has two keys corresponding to the two relationship types described above (hasprinter-Person and hasauthor-Person). The `count` field for each of those relationship types represents how many nodes (or pieces of content) have that specific relationship type.

#### GET Parameters

The following GET parameters allow you to page through nodes and edges, restrict the types of results, and even collapse certain indirect relationships.

| Parameter | Purpose                                                                                                                                                                                                                                                                                                                                                           | Example |
|---|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---|
| `per_type_limit` | Max number of connected nodes to return per relationship type (default: 20)                                                                                                                                                                                                                                                                                       | `?per_type_limit=50` |
| `per_type_skip` | Number of connected nodes to skip per relationship type — useful for pagination (default: 0)                                                                                                                                                                                                                                                                      | `?per_type_skip=20` |
| `meta-only` | If present (no value needed), suppresses nodes/edges from the response and only returns the `meta` section with counts                                                                                                                                                                                                                                            | `?meta-only` |
| `is-seed` | If present, ensures the focal content node itself is included in the `nodes` list even if it has no connections in this result set                                                                                                                                                                                                                                | `?is-seed` |
| `target-ct` | Restricts results to a single related content type                                                                                                                                                                                                                                                                                                                | `?target-ct=Person` |
| `filters` | Comma-separated list of `ContentType:ContentViewURI` pairs. Only nodes belonging to the specified Content View for that type are included.                                                                                                                                                                                                                        | `?filters=Person:/corpus/.../cv/abc` |
| `hidden` | Comma-separated list of content type names to exclude entirely from results                                                                                                                                                                                                                                                                                       | `?hidden=Tag,Category` |
| `collapses` | Comma-separated "collapse" specs in the form `FromCT-ProxyCT-ToCT`. This suppresses the intermediate proxy nodes and instead creates direct edges between `FromCT` and `ToCT`, annotated with a `freq` count indicating how many paths passed through the proxy. Multiple proxy types can be chained using `.` as a separator (e.g. `Author-Book.Chapter-Verse`). | `?collapses=Author-Book-Chapter` |


### The Pattern Count Endpoint

This endpoint counts how many times a user-specified graph traversal pattern is present in the Neo4J graph. This is useful for answering questions like, "How many Documents are connected to a specific Person through a specified pattern of association?"

The URL pattern looks like this:

`https://[ your.corpora.domain ]/api/corpus/[ corpus ID ]/[ content type name ]/pattern-count/`

Since you're specifying a content type with a URL parameter in the URL, that content type becomes the first "node" of your pattern. The rest of the pattern is specified using the `pattern` get parameter. The value for that parameter is dictated by the pattern convention explained below.

#### The Pattern Convention

The pattern convention used by Corpora is a stripped down riff on [Neo4J's Cypher](https://neo4j.com/product/cypher-graph-query-language/) conventions for notating nodes and edges. Imagine you want to know how many books are published by authors from New York, and you have three content types: Book, Author, and City. These three content types are wired up by virtue of Book having an "author" field of type cross-reference referring to the Author content type, and Author having a "city" field of type cross-reference referring to the City content type.

To build this pattern, we need to determine our starting point. In this case we'll start with Book, and so we're going to query the Pattern Count endpoint using `Book` as the content type in our URL parameter.

Our next step in the pattern is `Author`, so we're going to need to provide that in our `pattern` GET parameter. To make the query most effecient, we should also specify the "direction" of the relationship from Book to Author. Since Book has a field that points to Author, we'll prefix our next step of the pattern with a direction like so:

`-->(Author)`

Since the next step is from Author to City, and since Author has a field that points to city, we should provide the next step in our pattern:

`-->(Author) -->(City)`

**Note:** steps in the pattern are delimited by a space! Since we want to count how many books are published by authors from New York, not just any city will do. We need to be more specific. Let's assume "New York" exists as a piece of content of type City and its ID is `62f554a9837071d8c49109de`. We can specify that ID in our pattern using square brackets like so:

`-->(Author) -->(City[62f554a9837071d8c49109de])`

Now that we have our pattern, let's put it all together:

`https://[ your.corpora.domain ]/api/corpus/[ corpus ID ]/Book/pattern-count/?pattern=-->(Author) -->(City[62f554a9837071d8c49109de])`

Assuming there are around 40 books published by authors from New York in our dataset, the response would look like this:

```JSON
{ "count": 42 }
```

#### Pattern Count Parameters

| Parameter | Purpose | Example |
|---|---|---|
| `pattern` | **(Required)** A space-delimited graph traversal pattern string describing the path to match in Neo4J. Each step is a content type name in parentheses, with optional `-->` or `<--` direction arrows. A comma-separated list of content IDs in square brackets can be appended within the parentheses to constrain a step to specific items. | `?pattern=(Person) --> (Book)` |
| `terms-aggregation` | If present (no value needed), changes the response format to a per-item breakdown instead of a single count (see below). | `?terms-aggregation` |


**With `terms-aggregation`** — returns a mapping from each matching root content ID to the list of leaf content IDs it is connected to through the pattern:

```JSON
{
  "rootID1": ["leafID_a", "leafID_b"],
  "rootID2": ["leafID_c"],
  ...
}
```

Results are ordered by descending leaf count (the root with the most connections appears first).

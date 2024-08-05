# Developing

Corpora was built with the DH developer in mind just as much as the DH scholar. It was created as a way to flexibly handle a wide variety of DH projects with minimal effort while also empowering the developer to focus on the more innovative aspects of a given project. Below are detailed the affordances of corpora tailored specifically for developers, listed in order of complexity.



## Content Type Templates

From a developer's perspective, a [Content Type](/#content-type) in Corpora is a class whose properties and methods are largely defined by the Content Type Manager (essentially a data schema editor) available on the Admin tab of a given corpus. Content Type Templates are the convention Corpora uses to allow developers to control how instances of content get *rendered*, whether as a textual label, an HTML snippet, a JavaScript component, an XML document, etc. This rendering is done using [the Jinja2-style Django template convention](https://docs.djangoproject.com/en/5.0/ref/templates/), and indeed it's recommended to refer to Django's documentation when editing or creating templates (particularly as a reference for [Django's built-in template tags](https://docs.djangoproject.com/en/5.0/ref/templates/builtins/#built-in-tag-reference)).

### Editing Label Templates

By way of example, let's consider the following Content Type used to keep track of named entities throughout a corpus of XML documents:

![Entity Content Type](assets/img/content_type_templates_entity_example.png "Entity Content Type")

There are four fields defined for this Content Type, which means any instance of this content will be an object with at least four properties. If we were to name an instance of this class `Entity`, then you'd access its four properties like this using pseudocode:

```python
Entity.xml_id
Entity.entity_type
Entity.name
Entity.uris
```

There are also always three more hidden properties available for any instance of Content:

```python
Entity.id       # a unique, alphanumeric identifier
Entity.uri      # a unique URI for this content which includes its corpus ID
Entity.label    # a textual representation of the content
```

The `label` property for any given piece of content in Corpora is generated using the template called "Label" which can be edited using the Content Type Manager.

To edit the Label template, go to the Admin tab of your corpus, scroll to the Content Type Manager, and expand out the tray for a given Content Type. Scroll to the bottom of that tray, and locate in the footer of the table that lists the fields for your Content Type the dropdown prefixed with the label "Edit Template." Click the "Go" button to begin editing the template used by Corpora to generate textual labels for that Content Type:

![Template Editor](assets/img/content_type_templates_label_example.png "Template Editor")

In this particular case, the template for our label looks like this:

```django
{{ Entity.name }} ({{ Entity.entity_type }})
```

When editing a Content Type template in Corpora, the template's "namespace" has available to it an instance of the content *named the same as the Content Type* (i.e. `Entity`). Django's templating system has a convention whereby you can dynamically insert the value for an object's property by surrounding it with double curly-braces. So to output the value of your Entity's `name` property in a template, you'd use:

```django
{{ Entity.name }}
```

Notice this is how our template example begins. The rest of the example includes a space, open parenthesis, the output of the value for the Entity's `entity_type` field, and then a closing parenthesis. Given this template, if our instance of the Entity Content Type had the value "Maria Edgeworth" for the field `name`, and "PERSON" for the field `entity_type`, the textual label for that piece of content would look like this:

```django
Maria Edgeworth (PERSON)
```

Django's templating system is powerful, as it also provides affordances for boolean logic in the form of if/else statements. Let's say we want our label template to be a little more sophisticated by having it provide default values for fields that have no value. In this case, we'll leverage Django's built-in `{% if ... %}` [syntax](https://docs.djangoproject.com/en/5.0/ref/templates/builtins/#if):

```django
{% if Entity.name %}{{ Entity.name }}{% else %}Unknown{% endif %} ({% if Entity.entity_type %}{{ Entity.entity_type }}{% else %}UNKNOWN{% endif %})
```

Using this new template, if the Entity's `name` property has no value, the string "Unknown" will be output. Similarly, if `entity_type` has no value, "UNKNOWN" will be output.

Note that when you make changes to a template in Corpora's Content Type Manager, you must click the orange "Save" button on the "Edit Template" modal, *and must also* click the orange "Save Changes" button in the footer of the Content Type Manager for template changes to be "committed" to your data schema. Also note that when the Label template is changed, Corpora automatically fires off a reindexing task for the Content Type in question, as well as for any other Content Types in your corpus that reference the Content Type in question. Depending on how many instances of these Content Types you have in your corpus, this reindexing may take some time.

### Creating New Templates

Beyond specifying how content labels get created, Corpora's Content Type templating system allows you to create almost any kind of web-based representation of your content by allowing you to build a template and choose the appropriate [MIME type](https://en.wikipedia.org/wiki/Media_type) for that representation.

Building off our `Entity` example, let's say you wanted to create [TEI XML](https://tei-c.org/) representations for entities in your corpus. In the Content Type Manager for your corpus, you'd expand out the tray for your Content Type and, next to the "Go" button for editing an existing template, you'd click the "New Template" button to bring up the template editor:

![XML Template Example](assets/img/content_type_templates_xml_example.png "XML Template Example")

Give your template a URL-friendly name (no spaces or special characters), provide the content for your template, and choose an appropriate MIME Type (in this case, text/xml so we can serve up XML for the output of this template). In case the image above is too small or blurry, here's the content for this template:

```xml
<person xml:id="{{ Entity.xml_id }}">
   <persName>{{ Entity.name }}</persName>
</person>
```

Click the "Save" button on the template editing modal, and then click "Save Changes" at the bottom of the Content Type Manager. Once this happens, your new template is available to be rendered.

### Viewing Rendered Templates

To view the output of a template for an instance of content, you'll need to construct a URL that follows this convention:

```html
[Your Corpora Instance]/corpus/[Corpus ID]/[Content Type]/[Content ID]/?render_template=[Template Name]
```

In this example, let's assume your Corpora instance is hosted at `https://mycorpora.org`, your Corpus ID is `62f554a9837071d8c4910dg`, the Content Type is `Entity`, the ID for your instance of Entity is `6691462b32399974cfc2cb1a`, and the template you want to render is our new `TEI-XML-Person` template. Given these assumptions, the URL would look like:

```html
https://mycorpora.org/corpus/62f554a9837071d8c4910dg/Entity/6691462b32399974cfc2cb1a/?render_template=TEI-XML-Person
```

Your browser should then display the rendered output for your content as an XML document (screenshot from Google Chrome):

![XML Output](assets/img/content_type_templates_xml_output.png "XML Output")

## The Corpus API for Python

The corpus API for Python does most of the heavy lifting behind the scenes in terms of the C.R.U.D. (creating, reading, updating, and deleting) operations on corpus data. Understanding how to use it is crucial to using the corpus iPython notebook and writing plugins for Corpora. At its heart, the API leverages [MongoEngine](https://docs.mongoengine.org/)--an ORM for MongoDB designed to behave similarly to the [SQL-oriented ORM baked into Django](https://docs.djangoproject.com/en/5.0/topics/db/models/). In fact, each corpus or content object is a [MongoEngine Document](https://docs.mongoengine.org/guide/defining-documents.html) under the hood, and when you query for content using the corpus API, you're actually working with [MongoEngine QuerySets](https://docs.mongoengine.org/guide/querying.html). As such, the majority of the documentation for the corpus API is covered by MongoEngine's documentation, so much of the documentation here will be in the form of examples.

### Creating a Corpus

```python
from corpus import Corpus

my_corpus = Corpus()
my_corpus.name = "MTC"
my_corpus.description = "My Test Corpus"
my_corpus.save()
```

Upon running the above script, the `my_corpus` variable will be an instance of [mongoengine.Document](https://docs.mongoengine.org/apireference.html#mongoengine.Document). After saving it, the `id` property of `my_corpus` will be a BSON ObjectId, which is how MongoDB uniquely identifies each document. The alphanumeric string representation of the ObjectId can be acquired like so:

```python
my_corpus_id_as_a_string = str(my_corpus.id)
```

### Retrieving a Corpus

```python
from corpus import get_corpus

my_corpus = get_corpus('6661e28c4399e45f0bfd2121')
```

The `get_corpus` function will accept as its first parameter either a string or a BSON ObjectId and will return an instance of the Corpus object, which is ultimately a MongoEngine Document with the following properties:

| Property      | Data Type  | Purpose                                                                                                                                                    |
|---------------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | string     | To provide a brief project label, typically an acronym.                                                                                                    | 
| description   | string     | To provide a full project descriptor, typically the spelled out version of the project's name.                                                             |
| uri           | string     | This property is generated when the corpus is first saved, and it provides a unique URI for the corpus as it exists on the instance of Corpora hosting it. |
| path          | string     | Generated upon first save. It contains the file path to the corpus' files within the Corpora Docker container, should it have any.                         |
| kvp           | dictionary | KVP stands for "key/value pairs," and it's intended to house arbitrary metadata (rarely used).                                                             |
| files         | dictionary | The keys for the dictionary are unique hashes based on the file's path. These are long alphanumeric strings. The values are [File objects](#Files).        |
| repos         | dictionary | The keys are the name given to the repo, and the values are [Repo objects](/#repos).                                                                       |
| open_access   | boolean    | A flag for determining whether a corpus is open access, making its read-only API publicly available.                                                       |
| content_types | dictionary | The keys are the name of a given Content Type, and the values are a dictionary specifying the metadata for a given Content Type and its fields.            |
| provenance    | list       | A list of completed jobs for this corpus.                                                                                                                  |

A corpus object also has several methods which will be covered in subsequent sections.

### Creating Content

With a corpus object in hand, you can create content using the corpus' `get_content` method. This example assumes you have a Content Type called "Document" in your corpus:

```python
new_document = my_corpus.get_content('Document')
new_document.title = "On Beauty"
new_document.author = "Zadie Smith"
new_document.save()
```

Calling your corpus' `get_content` method by only passing in the Content Type name will return an instance of a MongoEngine document with that Content Type's fields as properties to be set. Once you've set those field values, you call the `save` method to save the content and assign it a unique ID.

*Note:* When saving content, the data is first saved to MongoDB. Post-save events then fire which also *index* the content in Elasticsearch and *link* the data in Neo4J. As such, saving content can be relatively time consuming, especially when saving in bulk. In cases where bulk saving needs to occur, you can turn off indexing and/or linking like so:

```python
# Saves to MongoDB and Neo4J, but not Elasticsearch:
new_document.save(do_indexing=False)

# Saves to MongoDB and Elasticsearch, but not Neo4J:
new_document.save(do_linking=False) 

# Saves only to MongoDB:
new_document.save(do_indexing=False, do_linking=False)
```

If you later want to fire off a job to index and link all of your content, you can do so like this:

```python
my_corpus.queue_local_job(task_name="Adjust Content", parameters={
    'content_type': 'Document',
    'reindex': True,
    'relabel': True
})
```

### Retrieving Content

Your corpus' `get_content` method is also useful for retrieving content when you know either the ID or exact field values for your content. When using `get_content` to retrieve content, you're ultimately querying MongoDB:

```python
# Query for a single piece of content with the ID known:
content = my_corpus.get_content('Document', '5f623f2a52023c009d73108e')
print(content.title)
"On Beauty"

# Query for a single piece of content by field value:
content = my_corpus.get_content('Document', {'title': "On Beauty"}, single_result=True)

# Query for multiple pieces of content by field value:
contents = my_corpus.get_content('Document', {'author': "Zadie Smith"})
for content in contents:
    print(content.title)
"White Teeth"
"On Beauty"

# Query for all content with this Content Type:
contents = my_corpus.get_content('Document', all=True)
```

When retrieving a single piece of content, you receive a MongoEngine Document. When retrieving multiple pieces of content, you receive a MongoEngine QuerySet. QuerySets are generators (can be iterated over using a for-loop), but also have their own methods, like `count`:

```python
contents = my_corpus.get_content('Document', all=True)
contents.count()
42
```

### Editing Content

Once you've retrieved a single piece of content using `get_content`, you can directly edit its field values and then call `save` to edit it:

```python
content = my_corpus.get_content('Document', '5f623f2a52023c009d73108e')
content.published_year = 2005
content.save()
```

### Deleting Content

Deleting content is as simple as calling the MongoEngine Document's `delete` method:

```python
content = my_corpus.get_content('Document', '5f623f2a52023c009d73108e')
content.delete()
```

*Note:* because content can be cross-referenced in arbitrary ways, deleting content saves a stub in the database that tells Corpora to sweep for instances of other content that references the deleted content so as to remove those references. When deleting large quantities of content, this can cause a backlog of deletion stubs. If you know you'll be deleting a large amount of content, and you also feel certain there's no need to track these deletions in order to hunt for stale content references, you can skip the creation of a deletion stub like so:

```python
content.delete(track_deletions=False)
```

### Working with Cross-Referenced Content

Much of the value of Corpora's Neo4J database is in its ability to keep track of the way your content is related, allowing the interface to visualize these connections. Content becomes "related" to other content via fields of type `cross-reference`.

By way of example, let's assume you're working with a corpus that has two Content Types: `Entity` and `Letter`. And let's say that the `Letter` has a field called `recipient` of type `cross-reference` that specifically references the type `Entity`. In this way, a `Letter` can reference a specific `Entity` via its `recipient` field. Let's create an Entity and a Letter, and "relate" them appropriately:

```python
entity = my_corpus.get_content('Entity')
entity.name = "Elizabeth Barrett Browning"
entity.save()

letter = my_corpus.get_content('Letter')
letter.contents = "Real warm spring, dear Miss Barrett, and the birds know it, and in Spring I shall see you, really see you..."
letter.recipient = entity.id
letter.save()
```

Note how when specifying the value of the `recipient` field for our instance of `Letter`, we used the `id` property of `Entity`. If the "multiple" box is checked when creating a field of type `cross-reference`, the field is actually a list, and so content ID's must be appended to the list:

```python
letter.recipients.append(entity.id)
letter.save()
```

You may query for content using cross-referenced fields, and the easiest way to do this is with the ObjectId (or its string representation) of the cross-referenced content. For example:

```python
letters_to_elizabeth = my_corpus.get_content('Letter', {'recipient': '66a166e56cf2fb23103b58b2'})
```

You may also access the values of nested fields for cross-referenced content like so:

```python
first_letter = letters_to_elizabeth[0]
print(first_letter.recipient.name)
"Elizabeth Barrett Browning"
```

### Working with Files

In Corpora, files belonging to a corpus or to a piece of content are ultimately registered as `File` objects, which themselves are a MongoEngine Embedded Document with the following properties:

| Property        | Data Type | Purpose                                                                                                                                                                 |
|-----------------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| path            | string    | To keep track of the file path as it exists inside the Corpora container.                                                                                               |
| primary_witness | boolean   | To flag whether the file should be the primary "witness" or digital surrogate for the content in question. Currently only used in the context of the `Document` plugin. |
| basename        | string    | The filename of the file (without the path), i.e. "data.csv"                                                                                                            |
| extension       | string    | The extension of the file, i.e. "csv"                                                                                                                                   |
| byte_size       | integer   | The size of the file in bytes                                                                                                                                           |
| description     | string    | Human-readable description of the file                                                                                                                                  |
| provenance_type | string    | To track what kind of thing originated this file, i.e. "Tesseract OCR Job"                                                                                              |
| provenance_id   | string    | A unique identifier for the thing that originated this file, i.e. "4213"                                                                                                |
| height          | integer   | The height in pixels of the file (if it's an image)                                                                                                                     |
| width           | integer   | The width in pixels of the file (if it's an image)                                                                                                                      |
| iiif_info       | dict      | A dictionary representing the kind of metadata you get when querying for /info.json on a IIIF server                                                                    |  

While those properties can be helpful, the only required property when creating a `File` object to represent a file is the `path`. The path of a file is always relative to the Corpora container. When the file is directly associated with a corpus, it lives in the `/files` directory, itself living in the directory specified by the corpus' `path` property. A directory is created in the Corpora container any time a corpus is created, and its path always looks like `/corpora/[corpus ID]`. As such, files directly associated with a corpus should live inside the `/corpus/[corpus ID]/files` directory.

The best way to associate a file with a corpus is via the corpus' homepage by going to the "Metadata" tab and clicking the orange "Import" button next to "Corpus Files." When you import files like this, it saves them in a `files` directory living inside of the directory specified in the `path` property of the corpus. Imported files are also registered in the `files` dictionary of your corpus object.

The keys for the `files` dictionary of a corpus are hashes based on the file's path--this is to provide a URL-friendly way of accessing them. This makes retrieving them programmatically in Python a little unintuitive, however. Let's say you upload a file called `entities.csv` to your corpus. To access that file with Python, you'll need to get its path like so:

```python
entities_csv_path = None
for file_key in my_corpus.files.keys():
    if 'entities.csv' in my_corpus.files[file_key].path:
        entities_csv_path = my_corpus.files[file_key].path
```

Content Types can also specify "File" as a type of field, and in those cases, you may directly access the `path` property of the file (no intervening dictionary with file key hashes):

```python
photo = my_corpus.get_content('Photo', '66a166e56cf2fb23103b6h7')
photo.original_file.path
```

When files belong to an instance of content (rather than directly associated with a corpus), that piece of content gets its own `path` property and a directory is created for it (directories are normally not created for content--only when they have files associated with them). Content paths always look like this:

`/corpora/[corpus ID]/[Content Type]/[breakout directory]/[content ID]`

Given that millions of instances of a Content Type could exist for a corpus, Corpora implements a "breakout directory" to prevent any one directory from containing millions of subdirectories!

Much like with a corpus, files associated with content live inside the `/files` subdirectory of a content instance's path, i.e.:

`/corpora/[corpus ID]/[Content Type]/[breakout directory]/[content ID]/files`

When programmatically associating a file to a corpus or piece of content, it's important for that file to live in the correct place, as this allows all the files belonging to a corpus to be exported and restored appropriately.

To programmatically associate a file directly with a corpus, first upload it to the corpus' appropriate `/files` subdirectory and make note of its full path. Then:

```python
from corpus import get_corpus, File

# store the path to the file in a variable
my_file_path = '/corpora/6661e28c4399e45f0bfd2121/files/data.csv'

# retrieve your corpus
my_corpus = get_corpus('6661e28c4399e45f0bfd2121')

# create an instance of the File object by using its "process" method
# which takes at minimum the path to the file
my_file = File.process(my_file_path)

# generate a file key for storing the file in the corpus
my_file_key = File.generate_key(my_file_path)

my_corpus.files[my_file_key] = my_file
my_corpus.save()
```

Note the use of the `process` class method of File. That method takes a file path, checks to see if the file exists, gathers some minimal metadata about the file (like file size), and returns a `File` object. Because files directly associated with a corpus are stored using a file key, we generate one with the `generate_key` method of File.

## The Corpus Notebook

Corpora makes available to admins and corpus Editors the ability to launch an iPython notebook associated with your corpus. This is especially useful for loading and transforming data, or for developing code that will eventually live as a Task inside of a plugin.

### Launching the Notebook

To launch the corpus notebook, navigate to your corpus' homepage and click on the "Admin" tab. Click the orange "Launch Notebook" button to the right of the "Running Jobs" section. This will cause the page to reload, and a message should appear saying `Notebook server successfully launched! Access your notebook here.` Click on the "here" link to open your notebook in a new browser tab.

### Setting up the Corpus Python API

Once you've opened your notebook, you'll see that the first cell has been created for you. In it is code that must be run in order for you to make use of the Corpus Python API. Once you run that cell, you'll have access to the variable `my_corpus` which is an instance of the [Corpus object](#retrieving-a-corpus).

### Python Packages

For a list of Python packages installed in your notebook environment, see the [requirements.txt](https://github.com/bptarpley/corpora/blob/master/app/requirements.txt) file used by the build process for the Corpora container. This list of packages has been kept relatively minimal in order to keep the size of the Corpora container manageable. That said, additional packages can be installed using the following methods.

#### Installing at Runtime

To install a given package (like, say, `pandas`) at runtime, simply prefix a `pip install` command with an exclamation point in a notebook cell and execute it. For example:

```shell
!pip install pandas
```

This will prompt pip (the Package Installer for Python) to download and install the package to the "user installation" of Python. Specifically, this is found at `/conf/plugin_modules/lib/python3.11/site-packages` inside the Corpora container. As instructed in the [deployment documentation](/deploying/#prerequisites), you should have various subdirectories inside a data directory on your host machine mounted inside of Corpora, and one of those subdirectories is `conf`, corresponding to the `/conf` path inside the Corpora container. As such, assuming the Corpora data directory you set up on your host machine is at `/corpora/data`, you'll find packages installed in this manner in `/corpora/data/conf/plugin_modules/lib/python3.11/site-packages` on your host machine. Because these files are living in a directory mounted from your host computer, *any packages you install at runtime will persist* until you delete or uninstall them.

#### Installing via Plugin

Corpora is built with a plugin architecture allowing you to extend its functionality. One way to ensure that certain Python packages are installed when the Corpora container first launches is to specify them in a `requirements.txt` file in the directory for your plugin. Note that for Corpora to look for that `requirements.txt` file, *your plugin must be enabled* as instructed [here](/managing/#installing-plugins), and enabling a plugin (as well as installing packages specified via `requirements.txt`) requires that you restart the Corpora container. Once Corpora has installed your packages in this way, they are persisted at the same `/conf/plugin_modules/lib/python3.11/site-packages` location and won't have to be installed during subsequent restarts.

### Limitations

While your notebook is saved as you go and can be returned to over multiple sessions, at this time Corpora only supports a single notebook per corpus. Also, at this time *only a single notebook can be running on a given instance of Corpora at any given time*. As such, should you be working in your notebook, and should another user attempt to launch their own corpus notebook, your notebook will be shut down and they will have the active notebook session.

## Corpora Plugins

Corpora's plugin architecture allows you to extend the functionality of Corpora by adding custom Content Types, asynchronous Tasks, and even new REST API endpoints or public facing web pages. In this way, Corpora's codebase can remain relatively generic while the data schema and functionality of a custom project can be contained in a separate and distributable codebase.

### Minimum Requirements

For Corpora to recognize your plugin, you must choose a name for your plugin that adheres to the [Python convention for package and module names](https://peps.python.org/pep-0008/#package-and-module-names), i.e. short, all lowercase, and usually one word or acronym, though underscores are okay if necessary (no other special characters or spaces). For the purposes of this documentation, we'll assume you're creating a plugin named `survey`.

Having chosen your name, create a directory with that name, and inside it place an empty file named `__init__.py`:

```
survey
│   __init__.py
```

Technically, placing this directory in the correct place, enabling the plugin, and restarting Corpora according to [these instructions](/managing/#installing-plugins) is all that is required for your plugin to work. At this point, however, the `survey` plugin does nothing useful. See below for the various ways to build functionality for your plugin.

### Custom Content Types

Often, the various tasks and functionality of your plugin require specialized Content Types for storing idiosyncratic data. The `tesseract` plugin, for instance, requires a Content Type called `TesseractLanguageModel` in order to store models for specific languages or fonts that can be trained using Corpora's interface.

As for our `survey` plugin, let's create some Content Types to keep track of surveys, questions, sessions, and responses. The easiest way to go about this is to [create a new corpus](/#creating-a-corpus) and use the Content Type Manager to [craft your Content Types](/#creating-content-types). Here are the various Content Types we'll create:

**Survey**

| Field | Label | Data Type      |
|-------|-------|----------------|
| name  | Name  | Text (English) |
| open  | Open? | Boolean        |

**Question**

| Field         | Label         | Data Type                |
|---------------|---------------|--------------------------|
| survey        | Survey        | Cross-reference (Survey) |
| query         | Query         | Text (English)           |
| query_choices | Query Choices | Text (English), multiple |
| order         | Order         | Number                   |

**Session**

| Field            | Label            | Data Type                |
|------------------|------------------|--------------------------|
| survey           | Survey           | Cross-reference (Survey) |
| respondent_name  | Respondent Name  | Text (English)           |
| respondent_email | Respondent Email | Keyword                  |
| date_taken       | Date Taken       | Date                     |

**Answer**

| Field    | Label    | Data Type                  |
|----------|----------|----------------------------|
| session  | Session  | Cross-reference (Session)  |
| question | Question | Cross-reference (Question) |
| response | Response | Text (English)             |

Once these Content Types have been created in your Content Type Manager, the easiest way to package them with your plugin is to download the JSON representation of your schema by clicking the export button in the footer of the Content Type Manager, which looks like this:

![Schema Export Button](assets/img/schema_export.png "Schema Export Button")

Clicking the schema export button will kick off a download of the JSON representation of your corpus as a file named `schema.json`. The next step is to edit that file with any text editor to convert the JSON to valid Python code. This can be done with three simple Find and Replace operations:

* Replace "true" with "True"
* Replace "false" with "False"
* Replace "null" with "None"

Once you've done this, create a file called `content.py` and save it in your plugin directory.

```
survey
│   __init__.py
│   content.py
```

Edit `content.py`, and create a single variable named `REGISTRY`, setting it equal to the Content Type schema you exported and converted to Python code. Here's a snippet of what the first lines of that file would look like now:

```python
REGISTRY = [
    {
        "name": "Survey",
        "plural_name": "Surveys",
        "fields": [
            {
                "name": "name",
                "label": "Name",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                ...
    ...
]
```

Assuming you've enabled this plugin and restarted Corpora, you should now be able to go into the Content Type Manager for any corpus and click on the schema import button, which looks like this:

![Schema Import Button](assets/img/schema_import.png "Schema Import Button")

This will open a pop-up modal with a text editor field for copying and pasting JSON. Below that field is a "Import plugin schema..." dropdown that looks like this:

![Plugin Schema Dropdown](assets/img/import_plugin_schema.png "Plugin Schema Dropdown")

This dropdown will allow you to select one or all of the Content Types associated with your plugin. Once you've made your choice, click the orange `Import` button. Your Content Types should now appear in the Content Type Manager. Be sure to click `Save Changes` to commit that schema to your corpus.

### Custom Tasks

Documentation forthcoming!





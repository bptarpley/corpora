# Corpora

*A Dataset Studio for the Digital Humanities*

## What is Corpora?

Corpora is Digital Humanities (DH) infrastructure—it's intended to be run by academic centers, libraries, or
project teams, and its purpose is to greatly accelerate the development of DH projects by serving as a database, a REST
API, a data collection/curation interface, and a Python-powered asynchronous task queue all wrapped into one. 

Corpora's name is the plural for "corpus" because it happily manages multiple, disparate datasets for a variety of
different projects. On the same instance of Corpora, you can host one project that contains millions of bibliographic
metadata records and another than contains hundreds of thousands of geolocated annotations for images. The limitations
for what you can host with Corpora are determined by your hardware, not the affordances of the software.

Among Corpora's affordances is a web-based interface for defining a data schema that is expected to evolve over time.
This is because it is extremely rare to define a perfect schema for appropriately keeping track of project data on the
first attempt. Projects happen iteratively, and so data schemas should be as effortlessly maleable as possible.

Once a schema has been defined for a project, Corpora dynamically generates web forms for collaborators to enter the
data. It also dynamically generates a read-only REST API for third party applications to query in order to provide, for
instance, a public, front-facing website for that project. Corpora's web interface makes use of this REST API to allow
scholars to search, sort, and explore the connections between their datapoints as they go about building their project.

Finally, Corpora is built to cater to a wide range of users, from scholars with little technical expertise to data
wranglers who want to leverage the power of Corpora's built-in iPython notebooks. Corpora also integrates a fully
asynchronous job queue allowing power users to run long-running jobs (such as optical character recognition, natural
language processing, TEI XML ingestion, etc.) on thousands of records at once.

## Who built it?

Corpora was built by Bryan Tarpley, Associate Research Scientist at the [Center of Digital Humanities Research at Texas A&M University](https://codhr.tamu.edu). Bryan very much hopes it will gain traction and become a robust, community developed open-source project.


## Documentation

Corpora's documentation is a work in progress, but you may find it [here](https://bptarpley.github.io/corpora) :)

## License

Corpora uses the [MIT license](https://opensource.org/license/mit)
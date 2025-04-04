# Plugins

Several plugins have been developed for use with Corpora, and some of them are listed below. They are listed here in order to both allow others to use them as well and also as a reference for developing new ones. For more explicit documentation on building custom plugins, see [here](/corpora/developing/#building-corpora-plugins). For instructions on how to deploy a plugin on your own instance of Corpora, see [here](/managing/#installing-plugins)



## The Document Plugin

The Document plugin is the only plugin Corpora comes bundled with. When creating a new corpus, users are prompted with the option to include the content types that come built-in with the Document plugin. These content types (and the custom functionality baked into them) are intended to provide users with a generic data structure capable of efficiently storing, displaying, and transcribing page-based documents. The Document plugin also integrates with both the Tesseract plugin and the Google Cloud Vision plugin to enable the running of OCR jobs using Corpora's asynchronous task queue.
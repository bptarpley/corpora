import json

from rest_framework.decorators import api_view
from manager.utilities import _get_context, get_scholar_corpus, _contains, _clean
from django.shortcuts import render, HttpResponse, redirect
from django.http import Http404
from elasticsearch_dsl import A


@api_view(['GET'])
def query(request, corpus_id):
    context = _get_context(request)
    content = {}

    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and 'ArcArtifact' in corpus.content_types:

        aggs = {}

        aggs['ArcFederation'] = A('nested', path='federations')
        aggs['ArcFederation'].bucket('names', 'terms', size=10000, field='federations.id')

        aggs['ArchiveParent'] = A('nested', path='archive')
        aggs['ArchiveParent'].bucket('names', 'terms', size=10000, field='archive.parent_path')

        aggs['ArcArchive'] = A('nested', path='archive')
        aggs['ArcArchive'].bucket('names', 'terms', size=10000, field='archive.id')

        aggs['ArcType'] = A('nested', path='types')
        aggs['ArcType'].bucket('names', 'terms', size=10000, field='types.id')

        aggs['ArcGenre'] = A('nested', path='genres')
        aggs['ArcGenre'].bucket('names', 'terms', size=10000, field='genres.id')

        aggs['ArcDiscipline'] = A('nested', path='disciplines')
        aggs['ArcDiscipline'].bucket('names', 'terms', size=10000, field='disciplines.id')

        aggs['decades'] = A('histogram', field='years', interval=10)

        if context['search']:
            context['search']['aggregations'] = aggs
            content = corpus.search_content(content_type='ArcArtifact', excludes=['full_text_contents'], **context['search'])
        else:
            content = corpus.search_content(content_type='ArcArtifact', excludes=['full_text_contents'], aggregations=aggs, general_query="*")

    else:
        raise Http404("You are not authorized to access this endpoint.")

    return HttpResponse(
        json.dumps(content),
        content_type='application/json'
    )


def bigdiva(request, corpus_id):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    return render(
        request,
        'bigdiva.html',
        {
            'corpus_id': corpus_id,
            'role': role,
            'response': response,
        }
    )


def uri_ascription(request, corpus_id, content_type, content_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    ascription = None

    if corpus:
        content_uri = '/corpus/{0}/{1}/{2}'.format(
            corpus_id,
            content_type,
            content_id
        )

        try:
            ascription = corpus.get_content('UriAscription', {'corpora_uri': content_uri})[0]
        except:
            ascription = None

    return render(
        request,
        'AscriptionWidget.html',
        {
            'corpus_id': corpus_id,
            'popup': True,
            'role': role,
            'attribution': ascription,
            'response': context,
        }
    )


def lincs_ttl(request, corpus_id, content_type, content_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    arts = []
    ttl = ''

    if corpus and content_id and content_type == 'ArcArtifact' and 'ArcArtifact' in corpus.content_types:
        arts.append(corpus.get_content('ArcArtifact', content_id, single_result=True))
    elif corpus and content_id and content_type == 'ArcArchive' and _contains(corpus.content_types, ['ArcArchive', 'ArcArtifact']):
        arts = corpus.get_content('ArcArtifact', {'archive': content_id})

    ttl = _generate_lincs_ttl(arts)

    return HttpResponse(
        ttl,
        content_type='text/turtle'
    )


def _generate_lincs_ttl(artifacts):
    globals = {}

    tab = '    '

    role_labels = {
        'ART': 'Visual Artist',
        'AUT': 'Author',
        'EDT': 'Editor',
        'PBL': 'Publisher',
        'TRL': 'Translator',
        'CRE': 'Creator',
        'ETR': 'Etcher',
        'EGR': 'Engraver',
        'OWN': 'Owner',
        'ARC': 'Architect',
        'BND': 'Binder',
        'BKD': 'Book designer',
        'BKP': 'Book producer',
        'CLL': 'Calligrapher',
        'CTG': 'Cartographer',
        'COL': 'Collector',
        'CLR': 'Colorist',
        'CWT': 'Commentator',
        'COM': 'Compiler',
        'CMT': 'Compositor',
        'DUB': 'Dubious author',
        'FAC': 'Facsimilist',
        'ILU': 'Illuminator',
        'ILL': 'Illustrator',
        'LTG': 'Lithographer',
        'PRT': 'Printer',
        'POP': 'Printer of plates',
        'PRM': 'Printmaker',
        'RPS': 'Repository',
        'RBR': 'Rubricator',
        'SCR': 'Scribe',
        'SCL': 'Sculptor',
        'TYD': 'Type designer',
        'TYG': 'Typographer',
        'WDE': 'Wood engraver',
        'WDC': 'Wood cutter'
    }

    # this ttl string will be built to contain the turtle representation of this artifact
    ttl = '''@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix crmpc: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix frbroo: <http://iflastandards.info/ns/fr/frbr/frbroo/> .
@prefix crmdig: <http://www.ics.forth.gr/isl/CRMdig/> .
@prefix cwrc: <http://id.lincsproject.ca/cwrc#> .\n\n'''

    for art in artifacts:
        if art and art.external_uri and art.title and art.agents and art.years:
            # todo: replace quote chars; vet use of has_note for accounting for art.description; how to rep relateds; how to represent ocr, full_text, full_text_url, full_text_contents; whether to include labels for things like <full_image> (present in examples but not spec sheet); how to represent subjects and coverages, ie ("Activism and involvement", "World War II -- Concentration camps -- Living conditions") from URI http://ddr.densho.org/ddr-csujad-29-59-1/

            #################################
            # MAIN STUB OF ARTIFACT         #
            #################################

            # main URI declaration
            ttl += '''<{uri}> a frbroo:F2_Expression ;\n'''.format(uri=art.external_uri.strip())

            # artifact "creation" node declaration (will specify agents and years later)
            ttl += '''{tab}frbroo:P94i_was_created_by <{id}_creation> ;\n'''.format(tab=tab, id=art.id)

            # browser URL
            ttl += '''{tab}crm:P1_is_identified_by <{url}> ;\n'''.format(tab=tab, url=art.url.strip())

            # label
            ttl += '''{tab}rdfs:label "{label}" ;\n'''.format(tab=tab, label=art.label.strip())

            # archive node declaration
            ttl += '''{tab}crm:P16i_was_used_for <{id}_contribution> ;\n'''.format(tab=tab, id=art.id)

            # title node declaration
            ttl += '''{tab}crm:P1_is_identified_by <{id}_title> ;\n'''.format(tab=tab, id=art.id)

            # alternative title node declaration
            if art.alt_title:
                ttl += '''{tab}crm:E33_E41_Linguistic_Appellation <{id}_alt_title> ;\n'''.format(tab=tab, id=art.id)

            # conflate ARC type, genres, disciplines, and freeculture indicator into LINCS "types" and declare nodes
            types = []
            for t in art.types:
                types.append(t.name.strip().replace(' ', '_'))

            for g in art.genres:
                types.append(g.name.strip().replace(' ', '_'))

            for d in art.disciplines:
                types.append(d.name.strip().replace(' ', '_'))

            if art.free_culture:
                types.append("Open_Access")

            if types:
                types = ['<' + t.strip() + '>' for t in types]
                ttl += '''{tab}crm:P2_has_type {types} ;\n'''.format(
                    tab=tab,
                    types=",\n{tab}{tab}".format(tab=tab).join(types)
                )

            # subject node declaration(s)
            if art.subjects:
                for subj in art.subjects:
                    ttl += '''{tab}crm:P129_is_about "{subject}" ;\n'''.format(tab=tab, subject=subj)
                    globals['''"{subject}" a skos:Concept .'''.format(subject=subj)] = True

            # coverage node declaration(s)
            if art.coverages:
                for cov in art.coverages:
                    ttl += '''{tab}crm:P67_refers_to "{coverage}" ;\n'''.format(tab=tab, coverage=cov)
                    globals['''"{coverage}" a crm:E53_Place .'''.format(coverage=cov)] = True

            # provenance node(s) declaration (handling art.sources)
            if art.sources:
                prov_nodes = []
                for prov_num in range(0, len(art.sources)):
                    prov_nodes.append("<{id}_provenance_{num}>".format(id=art.id, num=prov_num + 1))

                ttl += '''{tab}crm:P67i_is_referred_to_by {provs} ;\n'''.format(
                    tab=tab,
                    provs=",\n{tab}{tab}".format(tab=tab).join(prov_nodes)
                )

            # visual representations of artifact like image, thumbnail node declarations
            if art.image_url:
                ttl += '''{tab}crm:P138i_has_representation <{image}> ;\n'''.format(tab=tab, image=art.image_url.strip())

            if art.thumbnail_url:
                ttl += '''{tab}crm:P138i_has_representation <{thumb}> ;\n'''.format(tab=tab, thumb=art.thumbnail_url.strip())

            # markup representations of artifact like XML, HTML, SGML node declarations
            if art.source_xml:
                ttl += '''{tab}crm:P67i_is_referred_to_by <{xml}> ;\n'''.format(tab=tab, xml=art.source_xml.strip())

            if art.source_html:
                ttl += '''{tab}crm:P67i_is_referred_to_by <{html}> ;\n'''.format(tab=tab, html=art.source_html.strip())

            if art.source_sgml:
                ttl += '''{tab}crm:P67i_is_referred_to_by <{sgml}> ;\n'''.format(tab=tab, sgml=art.source_sgml.strip())

            # language node declaration
            if art.language:
                ttl += '''{tab}crm:P72_has_language <{lang}> ;\n'''.format(tab=tab, lang=art.language.strip())

            # description
            if art.description:
                ttl += '''{tab}crm:P3_has_note "{desc}" ;\n'''.format(tab=tab, desc=art.description.strip())

            # has_parts
            if art.has_parts:
                parts = ['<' + p.strip() + '>' for p in art.has_parts]
                ttl += '''{tab}crm:P148_has_component {has_parts} ;\n'''.format(
                    tab=tab,
                    has_parts=",\n{tab}{tab}".format(tab=tab).join(parts)
                )

            # is_part_ofs
            if art.is_part_ofs:
                parts = ['<' + p.strip() + '>' for p in art.is_part_ofs]
                ttl += '''{tab}crm:P148i_is_component_of {is_part_ofs} ;\n'''.format(
                    tab=tab,
                    is_part_ofs=",\n{tab}{tab}".format(tab=tab).join(parts)
                )

            # federation, date of edition, review date node declaration (expressed in terms of digital surrogacy)
            ttl += '''{tab}crm:P129i_is_subject_of <{id}_digital_surrogate> .\n\n'''.format(tab=tab, id=art.id)

            ttl += '''<{id}_digital_surrogate> a crm:E73_Information_Object ; 
    rdfs:label "ARC digial surrogate of {label}" ;
    crm:P2_has_type <ARC_digital_surrogate>, <http://vocab.getty.edu/aat/300379790> .\n\n'''.format(id=art.id, label=art.label.strip())

            if art.date_of_edition:
                ttl += '''<{id}_digital_surrogate> crm:P24i_was_created_by <{id}_digital_surrogate_creation> .

<{id}_digital_surrogate_creation> a crm:E65_Creation ;
    rdfs:label "Creation of ARC digital surrogate of {label}" ;
    crm:P2_has_type <https://www.wikidata.org/wiki/Q99231516> ; 
    crm:P4_has_time-span <{id}_digital_surrogate_creation_timespan> . 

<{id}_digital_surrogate_creation_timespan> a crm:E52_Time-Span ; 
    rdfs:label "Datetime of creation of ARC digital surrogate of {label}" ;
    crm:P82_at_some_time_within "{year}" ;
    crm:P82a_begin_of_the_begin "{year}-01-01T00:00:00"^^xsd:dateTime ;
    crm:P82b_end_of_the_end "{year}-12-31T23:59:59"^^xsd:dateTime .\n\n'''.format(
                    id=art.id,
                    label=art.label.strip(),
                    year=art.date_of_edition
                )

            if art.date_of_review:
                ttl += '''<{id}_digital_surrogate> crm:P16i_was_used_for <{id}_digital_surrogate_review>, <{id}_digital_surrogate_ingestion> .

<{id}_digital_surrogate_review> a crm:E7_Activity ; 
    rdfs:label "Review of ARC digital surrogate of {label}" ;
    crm:P2_has_type <Review> ; 
    crm:P9i_forms_part_of <{id}_digital_surrogate_ingestion> ;
    crm:P4_has_time-span <{id}_digital_surrogate_review_timespan> .

<{id}_digital_surrogate_review_timespan> a crm:E52_Time-Span ; 
    rdfs:label "Datetime of review of ARC digital surrogate of {label}" ;
    crm:P82_at_some_time_within "{year}" ;
    crm:P14_carried_out_by <{federation}> .

<{id}_digital_surrogate_ingestion> a crm:E7_Activity ; 
    rdfs:label "Ingestion of ARC digital surrogate of {label}" ;
    crm:P2_has_type <Ingestion> ;
    crm:P14_carried_out_by <ARC> ;
    crm:P4_has_time-span <{id}_digital_surrogate_ingestion_timespan> . 

<{id}_digital_surrogate_ingestion_timespan> a crm:E52_Time-Span ; 
    rdfs:label "Datetime of ingestion of ARC digital surrogate of {label}" ;
    crm:P82_at_some_time_within "{year}" ;
    crm:P82a_begin_of_the_begin "{year}-01-01T00:00:00"^^xsd:dateTime ;
    crm:P82b_end_of_the_end "{year}-12-31T23:59:59"^^xsd:dateTime .\n\n'''.format(
                    id=art.id,
                    label=art.label.strip(),
                    federation=art.federations[0].handle,
                    year=art.date_of_review
                )

                globals['''<Review> a crm:E55_Type .'''] = True
                globals['''<Ingestion> a crm:E55_Type .'''] = True
                globals['''<ARC> a crm:E39_Actor .'''] = True
                globals['''<{federation}> a crm:E39_Actor .'''.format(federation=art.federations[0].handle)] = True

            globals['''<ARC_digital_surrogate> a crm:E55_Type .'''] = True

            #################################
            # DEPENDENT NODES               #
            #################################

            # archive
            ttl += '''<{id}_contribution> a crm:E7_Activity ; 
    rdfs:label "Contribution of {label} to ARC" ; 
    crm:P2_has_type <Contribution_to_ARC> ; 
    crm:P14_carried_out_by <{archive}> .\n\n'''.format(
                id=art.id,
                label=art.label.strip(),
                archive=art.archive.handle
            )

            globals['''<Contribution_to_ARC> a crm:E55_Type ; 
    rdfs:label "Contribution to ARC" .'''] = True

            globals['''<{archive}> a crm:E39_Actor ; 
    rdfs:label "{archive_label}" .'''.format(
                archive=art.archive.handle,
                archive_label=art.archive.name.strip() if art.archive.name else art.archive.handle
            )] = True

            # title
            ttl += '''<{id}_title> a crm:E33_E41_Linguistic_Appellation ; 
    rdfs:label "{title}" ;
    crm:P190_has_symbolic_content "{title}" ;
    crm:P2_has_type <main_title> .\n\n'''.format(
                id=art.id,
                title=art.title.strip()
            )

            globals['''<main_title> a crm:E55_Type ; 
    rdfs:label "Main title" .'''] = True

            # alt title
            if art.alt_title:
                ttl += '''<{id}_alt_title> a crm:E35_Title ; 
    rdfs:label "{alt_title}" ;
    crm:P190_has_symbolic_content "{alt_title}" ;
    crm:P2_has_type <alternative_title> .\n\n'''.format(
                    id=art.id,
                    alt_title=art.alt_title.strip()
                )

                globals['''<alternative_title> a crm:E55_Type ; 
    rdfs:label "Alternative title" .'''] = True

            # LINCS types (ARC type, genres, disciplines, freeculture)
            if types:
                for t in types:
                    globals['''{type} a crm:E55_Type ; 
    rdfs:label "{type_label}" .'''.format(
                        type=t,
                        type_label=t.replace('<', '').replace('>', '').replace('_', ' ')
                    )] = True

            # provenance(s)
            if art.sources:
                for prov_num in range(0, len(art.sources)):
                    ttl += '''<{id}_provenance_{prov_num}> a crm:E33_Linguistic_Object ; 
    rdfs:label "Provenance statement about {label}" ; 
    crm:P190_has_symbolic_content "{prov}" ; 
    crm:P2_has_type <Provenance_note> .\n\n'''.format(
                        id=art.id,
                        prov_num=prov_num + 1,
                        label=art.label.strip(),
                        prov=art.sources[prov_num]
                    )

                globals['''<Provenance_note> a crn:E55_Type ; 
    rdfs:label "Provenance note" .'''] = True

            # visual representations
            if art.image_url:
                ttl += '''<{image}> a crm:E36_Visual_Item ; 
    rdfs:label "Full image of {label}" ;
    crm:P2_has_type <full_image> .\n\n'''.format(
                    image=art.image_url.strip(),
                    label=art.label.strip()
                )

                globals['''<full_image> a crm:E55_Type ; 
    rdfs:label "full image" .'''] = True

            if art.thumbnail_url:
                ttl += '''<{thumb}> a crm:E36_Visual_Item ; 
    rdfs:label "Thumbnail image of {label}" ;
    crm:P2_has_type <thumbnail_image> .\n\n'''.format(
                    thumb=art.image_url.strip(),
                    label=art.label.strip()
                )

                globals['''<thumbnail_image> a crm:E55_Type ; 
    rdfs:label "thumbnail image" .'''] = True

            # markup representations
            if art.source_xml:
                ttl += '''<{xml}> a crm:E73_Information_Object ;
    rdfs:label "XML source code for data of {label}" ;
    crm:P2_has_type <xml> .\n\n'''.format(
                    xml=art.source_xml.strip(),
                    label=art.label.strip()
                )

                globals['''<xml> a crm:E55_Type ;
    rdfs:label "XML document" .'''] = True

            if art.source_html:
                ttl += '''<{html}> a crm:E73_Information_Object ;
    rdfs:label "XML source code for data of {label}" ;
    crm:P2_has_type <html> .\n\n'''.format(
                    html=art.source_html.strip(),
                    label=art.label.strip()
                )

                globals['''<html> a crm:E55_Type ;
    rdfs:label "HTML document" .'''] = True

            if art.source_sgml:
                ttl += '''<{sgml}> a crm:E73_Information_Object ;
    rdfs:label "SGML source code for data of {label}" ;
    crm:P2_has_type <sgml> .\n\n'''.format(
                    sgml=art.source_sgml.strip(),
                    label=art.label.strip()
                )

                globals['''<sgml> a crm:E55_Type ;
    rdfs:label "SGML document" .'''] = True

            # language
            if art.language:
                globals['''<{lang}> a crm:E56_Language .'''.format(lang=art.language.strip())] = True

            # agents and dates (the creation node)
            agents = ["<{entity}_{role}>".format(entity=a.entity.name.strip(), role=a.role.name.strip()) for a in art.agents]

            ttl += '''<{id}_creation> a crm:E65_Creation ;
    rdfs:label "Creation of {label}" ;
    crm:P2_has_type cwrc:ProductionEvent, cwrc:PublishingEvent ;
    crmpc:P01i_is_domain_of {agents} ;  
    crm:P4_has_time-span <{id}_creation_timespan> .\n\n'''.format(
                id=art.id,
                label=art.label.strip(),
                agents=",\n{tab}{tab}".format(tab=tab).join(agents)
            )

            for agent in art.agents:
                globals['''<{name}_{role}> a crmpc:PC14_carried_out_by ; 
    rdfs:label "{name} in the role of {role_desc}" ;
    crmpc:P02_has_range <{name}> ;
    crmpc:P14.1_in_the_role_of <{role}> .'''.format(
                    name=agent.entity.name.strip(),
                    role=agent.role.name.strip(),
                    role_desc=role_labels.get(agent.role.name.strip(), 'Unknown Role')
                )] = True

                globals['''<{name}> a crm:E39_Actor ; 
    rfs:label "{name}" .'''.format(name=agent.entity.name.strip())] = True

                globals['''<{role}> a crm:E55_Type ; 
    rdfs:label "{role_desc}" .'''.format(
                    role=agent.role.name,
                    role_desc=role_labels.get(agent.role.name.strip(), 'Unknown Role')
                )] = True

            ttl += '''<{id}_creation_timespan> a crm:E52_Time-Span ; 
    rdfs:label "Datetime of creation of {label}" ;
    crm:P82_at_some_time_within "{date_value}" ; 
    crm:P82a_begin_of_the_begin "{first_year}-01-01T00:00:00"^^xsd:dateTime ; 
    crm:P82b_end_of_the_end "{last_year}-12-31T23:59:59"^^xsd:dateTime .\n\n'''.format(
                id=art.id,
                label=art.label.strip(),
                date_value=art.date_value,
                first_year=art.years[0],
                last_year=art.years[-1]
            )

    #################################
    # Globals                       #
    #################################

    for statement in globals.keys():
        ttl += statement + '\n\n'

    return ttl

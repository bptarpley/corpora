from subprocess import call
from PIL import Image

from django.utils.text import slugify
from huey.contrib.djhuey import db_task
from corpus import *
import os
import re
import numpy as np


REGISTRY = {
    "OCR Document with Calamari": {
        "version": "0.3",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Document",
        "configuration": {
            "parameters": {
                "collection": {
                    "value": "",
                    "type": "page_file_collection",
                    "label": "Page Image Collection",
                    "note": "Be sure to select a collection consisting of images."
                },
                "primary_witness": {
                    "label": "Make Primary Witness?",
                    "type": "choice",
                    "choices": [
                        "Yes",
                        "No"
                    ],
                    "value": "Yes",
                    "note": "If you have not yet OCR'd this document, or if you'd like to replace existing OCR results as the primary witness for this document, this should remain set to 'Yes.'"
                }
            },
        },
        "module": 'plugins.calamari.tasks',
        "functions": ['ocr_document_with_calamari', 'complete_ocr_document_with_calamari']
     }
}


@db_task(priority=2)
def ocr_document_with_calamari(job_id):
    job = Job(job_id)
    page_file_collection_key = job.configuration['parameters']['collection']['value']
    page_files = job.content.get_page_file_collection(job.corpus_id, job.content_id, page_file_collection_key)['page_files']
    primary_witness = job.configuration['parameters']['primary_witness']['value'] == 'Yes'
    num_pages = len(page_files.ordered_ref_nos)
    pages_per_worker = 5
    # what is pages allocated?

    pages_allocated = 0
    # understand following part
    while pages_allocated < num_pages:
        starting_page = pages_allocated
        ending_page = starting_page + pages_per_worker
        huey_task = ocr_pages_with_calamari(job_id, starting_page, ending_page, primary_witness)
        job.add_process(huey_task.id)
        pages_allocated = ending_page + 1

    job.set_status('running')


@db_task(priority=1, context=True)
def ocr_pages_with_calamari(job_id, starting_page, ending_page, primary_witness, task=None):
    job = Job(job_id)
    model_path = "/corpora/model_00023716.ckpt.json"

    page_file_collection_key = job.configuration['parameters']['collection']['value']
    page_files = job.content.get_page_file_collection(job.corpus_id, job.content_id, page_file_collection_key)['page_files']
    assigned_pages = page_files.ordered_ref_nos[starting_page:ending_page + 1]

    for ref_no, file in page_files:
        if ref_no in assigned_pages:
            os.makedirs("{0}/pages/{1}".format(job.content.path, ref_no), exist_ok=True)

            if os.path.exists(file['path']):
                print("file basename is the following @@ " + file['basename'])
                file_page_name = file['basename'][:-4]
                # base path for different outputs
                page_file_results = "{0}/pages/{1}/{2}_Calamari_{3}".format(
                    job.content.path,
                    ref_no,
                    page_file_collection_key,
                    ref_no
                )
                # build command to run for prediction
                command = [
                    "tesseract",
                    file['path'],
                    page_file_results,
                    "-l", "eng",
                    "hocr", "txt"
                ]

                if call(command) == 0:
                    # txt_file_obj = File.process(
                    #     page_file_results + '.txt',
                    #     desc='Plain Text',
                    #     prov_type='Calamari OCR Job',
                    #     prov_id=str(job_id),
                    #     primary=primary_witness
                    # )
                    # if txt_file_obj:
                    #     job.content.save_page_file(ref_no, txt_file_obj)


                    hocr_file_obj = File.process(
                        page_file_results + '.hocr',
                        desc='HOCR',
                        prov_type='Calamari OCR Job',
                        prov_id=str(job_id),
                        primary=primary_witness
                    )


                    if hocr_file_obj:
                        job.content.save_page_file(ref_no, hocr_file_obj)
                    lines_folder = ocr_segment_page_into_lines(job_id, page_file_results + '.hocr', file['path'], ref_no,
                                                               file_page_name)

                    if lines_folder is not None:
                        ocr_lines_with_calamari(job_id, lines_folder, model_path)
                        ocr_combine_output_files(job_id, lines_folder, file_page_name, ref_no )
    if task:
        job.complete_process(task.id)


# @db_task(priority=2, context=True)
def ocr_segment_page_into_lines(job_id, hocr_file_name, page_file_path, ref_no, file_page_name):
    job = Job(job_id)
    output_path = job.content.path + "/pages/" + ref_no + "/lines/"
    if not os.path.exists(output_path):
        os.mkdir(output_path)
    im = Image.open(page_file_path)
    f = open(hocr_file_name)
    file_name = job.configuration['parameters']['collection']['value']
    count = 0
    try:
        for line in f:
            listnew = re.findall('<span class=\'ocr_line\' id.* title=\"bbox (\\d*) (\\d*) (\\d*) (\\d*); baseline.*', line)
            if listnew:
                # print (int(listnew[0][0]))
                left = int(listnew[0][0])
                upper = int(listnew[0][1])
                right = int(listnew[0][2])
                lower = int(listnew[0][3])
                # im_crop = im.crop((hpos, vpos, hpos + width, vpos + height)).save("{}/{}".format(output_path, linefile),
                if lower - upper > 10:
                    im_crop = im.crop((left, upper, right, lower)).save(
                        "{}/{}_{}.png".format(output_path, file_page_name, count), quality=95)
                count += 1
    except Exception as e:
        print(e)
    # job.set_status('running')
    return output_path


# @db_task(priority=3, context=True)
def ocr_lines_with_calamari(job_id, lines_folder, model_path):
    try:
        job = Job(job_id)
        line_file_names = os.listdir(lines_folder)
        print(lines_folder)
        lines_folder = lines_folder + "/*.png"
        command = [
            "calamari-predict",
            "--checkpoint",
            model_path,
            "--files",
            lines_folder
        ]
        print (command)
        if call(command) == 0:
            print(command)
            print("command executed")
    except Exception as e:
        print (e)
#         calamari predict on model command

# def ocr_compile_lines_calamari(job_id, lines_results):
# #     compile and save as a document per page (or per book, how?)
#     print job_id


def ocr_combine_output_files(job_id, lines_folder, file_page_name, ref_no):
    print("Combining files for the page {}".format(file_page_name))
    f_write = open(lines_folder[:-6] + file_page_name + ".txt", "w+")
    try:
        all_files = os.listdir(lines_folder)
        for line_no in range(0, len(all_files)):
            curr_file = "{}_{}.pred.txt".format(file_page_name, line_no)
            if curr_file in all_files:
                # print("Currently combining {}".format(curr_file))
                f_read = open(lines_folder + curr_file, "r")
                f_write.write(f_read.read() + "\n")
                f_read.close()
    except Exception as e:
        print(e)






@db_task(priority=2)
def complete_ocr_document_with_calamari(job_id):
    job = Job(job_id)
    job.content.save(index_pages=True)
    job.complete(status='complete')


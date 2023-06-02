import os
import shutil
import tempfile

import pytest
from tests.utils import wrap_test_forked
from utils import zip_data, download_simple, get_ngpus_vis, get_mem_gpus, have_faiss

have_openai_key = os.environ.get('OPENAI_API_KEY') is not None

have_gpus = get_ngpus_vis() > 0

mem_gpus = get_mem_gpus()

# FIXME:
os.environ['TOKENIZERS_PARALLELISM'] = 'false'


@pytest.mark.skipif(not have_openai_key, reason="requires OpenAI key to run")
@wrap_test_forked
def test_qa_wiki_openai():
    return run_qa_wiki_fork(use_openai_model=True)


@wrap_test_forked
def test_qa_wiki_stuff_hf():
    # NOTE: total context length makes things fail when n_sources * text_limit >~ 2048
    return run_qa_wiki_fork(use_openai_model=False, text_limit=256, chain_type='stuff', prompt_type='human_bot')


@pytest.mark.xfail(strict=False,
                   reason="Too long context, improve prompt for map_reduce.  Until then hit: The size of tensor a (2048) must match the size of tensor b (2125) at non-singleton dimension 3")
@wrap_test_forked
def test_qa_wiki_map_reduce_hf():
    return run_qa_wiki_fork(use_openai_model=False, text_limit=None, chain_type='map_reduce', prompt_type='human_bot')


def run_qa_wiki_fork(*args, **kwargs):
    # disable fork to avoid
    # RuntimeError: Cannot re-initialize CUDA in forked subprocess. To use CUDA with multiprocessing, you must use the 'spawn' start method
    # because some other tests use cuda in parent
    # from tests.utils import call_subprocess_onetask
    # return call_subprocess_onetask(run_qa_wiki, args=args, kwargs=kwargs)
    return run_qa_wiki(*args, **kwargs)


def run_qa_wiki(use_openai_model=False, first_para=True, text_limit=None, chain_type='stuff', prompt_type=None):
    from gpt_langchain import get_wiki_sources, get_llm
    from langchain.chains.qa_with_sources import load_qa_with_sources_chain

    sources = get_wiki_sources(first_para=first_para, text_limit=text_limit)
    llm, model_name, streamer, prompt_type_out = get_llm(use_openai_model=use_openai_model, prompt_type=prompt_type)
    chain = load_qa_with_sources_chain(llm, chain_type=chain_type)

    question = "What are the main differences between Linux and Windows?"
    from gpt_langchain import get_answer_from_sources
    answer = get_answer_from_sources(chain, sources, question)
    print(answer)


def check_ret(ret):
    """
    check generator
    :param ret:
    :return:
    """
    rets = []
    for ret1 in ret:
        rets.append(ret1)
        print(ret1)
    assert rets


@pytest.mark.skipif(not have_openai_key, reason="requires OpenAI key to run")
@wrap_test_forked
def test_qa_wiki_db_openai():
    from gpt_langchain import _run_qa_db
    query = "What are the main differences between Linux and Windows?"
    ret = _run_qa_db(query=query, use_openai_model=True, use_openai_embedding=True, text_limit=None,
                     langchain_mode='wiki')
    check_ret(ret)


@wrap_test_forked
def test_qa_wiki_db_hf():
    from gpt_langchain import _run_qa_db
    # if don't chunk, still need to limit
    # but this case can handle at least more documents, by picking top k
    # FIXME: but spitting out garbage answer right now, all fragmented, or just 1-word answer
    query = "What are the main differences between Linux and Windows?"
    ret = _run_qa_db(query=query, use_openai_model=False, use_openai_embedding=False, text_limit=256,
                     langchain_mode='wiki')
    check_ret(ret)


@wrap_test_forked
def test_qa_wiki_db_chunk_hf():
    from gpt_langchain import _run_qa_db
    query = "What are the main differences between Linux and Windows?"
    ret = _run_qa_db(query=query, use_openai_model=False, use_openai_embedding=False, text_limit=256, chunk=True,
                     chunk_size=256,
                     langchain_mode='wiki')
    check_ret(ret)


@pytest.mark.skipif(not have_openai_key, reason="requires OpenAI key to run")
@wrap_test_forked
def test_qa_wiki_db_chunk_openai():
    from gpt_langchain import _run_qa_db
    # don't need 256, just seeing how compares to hf
    query = "What are the main differences between Linux and Windows?"
    ret = _run_qa_db(query=query, use_openai_model=True, use_openai_embedding=True, text_limit=256, chunk=True,
                     chunk_size=256,
                     langchain_mode='wiki')
    check_ret(ret)


@pytest.mark.skipif(not have_openai_key, reason="requires OpenAI key to run")
@wrap_test_forked
def test_qa_github_db_chunk_openai():
    from gpt_langchain import _run_qa_db
    # don't need 256, just seeing how compares to hf
    query = "what is a software defined asset"
    ret = _run_qa_db(query=query, use_openai_model=True, use_openai_embedding=True, text_limit=256, chunk=True,
                     chunk_size=256, langchain_mode='github h2oGPT')
    check_ret(ret)


@wrap_test_forked
def test_qa_daidocs_db_chunk_hf():
    from gpt_langchain import _run_qa_db
    # FIXME: doesn't work well with non-instruct-tuned Cerebras
    query = "Which config.toml enables pytorch for NLP?"
    ret = _run_qa_db(query=query, use_openai_model=False, use_openai_embedding=False, text_limit=None, chunk=True,
                     chunk_size=128, langchain_mode='DriverlessAI docs')
    check_ret(ret)


@pytest.mark.skipif(not have_faiss, reason="requires FAISS")
@wrap_test_forked
def test_qa_daidocs_db_chunk_hf_faiss():
    from gpt_langchain import _run_qa_db
    query = "Which config.toml enables pytorch for NLP?"
    # chunk_size is chars for each of k=4 chunks
    ret = _run_qa_db(query=query, use_openai_model=False, use_openai_embedding=False, text_limit=None, chunk=True,
                     chunk_size=128 * 1,  # characters, and if k=4, then 4*4*128 = 2048 chars ~ 512 tokens
                     langchain_mode='DriverlessAI docs',
                     db_type='faiss',
                     )
    check_ret(ret)


@wrap_test_forked
def test_qa_daidocs_db_chunk_hf_chroma():
    from gpt_langchain import _run_qa_db
    query = "Which config.toml enables pytorch for NLP?"
    # chunk_size is chars for each of k=4 chunks
    ret = _run_qa_db(query=query, use_openai_model=False, use_openai_embedding=False, text_limit=None, chunk=True,
                     chunk_size=128 * 1,  # characters, and if k=4, then 4*4*128 = 2048 chars ~ 512 tokens
                     langchain_mode='DriverlessAI docs',
                     db_type='chroma',
                     )
    check_ret(ret)

@wrap_test_forked
def test_qa_wiki_db_chunk_hf_weaviate():

    from gpt4all_llm import get_model_tokenizer_gpt4all
    model_name = 'llama'
    model, tokenizer, device = get_model_tokenizer_gpt4all(model_name)

    from gpt_langchain import _run_qa_db
    query = "What are the main differences between Linux and Windows?"
    # chunk_size is chars for each of k=4 chunks
    ret = _run_qa_db(query=query, use_openai_model=False, use_openai_embedding=False, text_limit=None, chunk=True,
                     chunk_size=128 * 1,  # characters, and if k=4, then 4*4*128 = 2048 chars ~ 512 tokens
                     langchain_mode='wiki',
                     db_type='weaviate',
                     prompt_type='wizard2',
                     model_name=model_name, model=model, tokenizer=tokenizer,
                     )
    check_ret(ret)

@pytest.mark.skipif(not have_openai_key, reason="requires OpenAI key to run")
@wrap_test_forked
def test_qa_daidocs_db_chunk_openai():
    from gpt_langchain import _run_qa_db
    query = "Which config.toml enables pytorch for NLP?"
    ret = _run_qa_db(query=query, use_openai_model=True, use_openai_embedding=True, text_limit=256, chunk=True,
                     chunk_size=256, langchain_mode='DriverlessAI docs')
    check_ret(ret)


@pytest.mark.skipif(not have_openai_key, reason="requires OpenAI key to run")
@wrap_test_forked
def test_qa_daidocs_db_chunk_openaiembedding_hfmodel():
    from gpt_langchain import _run_qa_db
    query = "Which config.toml enables pytorch for NLP?"
    ret = _run_qa_db(query=query, use_openai_model=False, use_openai_embedding=True, text_limit=None, chunk=True,
                     chunk_size=128, langchain_mode='DriverlessAI docs')
    check_ret(ret)


@wrap_test_forked
def test_get_dai_pickle():
    from gpt_langchain import get_dai_pickle
    with tempfile.TemporaryDirectory() as tmpdirname:
        get_dai_pickle(dest=tmpdirname)
        assert os.path.isfile(os.path.join(tmpdirname, 'dai_docs.pickle'))


@wrap_test_forked
def test_get_dai_db_dir():
    from gpt_langchain import get_some_dbs_from_hf
    with tempfile.TemporaryDirectory() as tmpdirname:
        get_some_dbs_from_hf(tmpdirname)


@wrap_test_forked
def test_make_add_db():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            msg1 = "Hello World"
            test_file1 = os.path.join(tmp_user_path, 'test.txt')
            with open(test_file1, "wt") as f:
                f.write(msg1)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("World")
            assert len(docs) == 1
            assert docs[0].page_content == msg1
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)

        # now add using new source path, to original persisted
        with tempfile.TemporaryDirectory() as tmp_user_path:
            msg2 = "Jill ran up the hill"
            test_file2 = os.path.join(tmp_user_path, 'test2.txt')
            with open(test_file2, "wt") as f:
                f.write(msg2)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path, add_if_exists=True,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("World")
            assert len(docs) == 2
            assert docs[0].page_content == msg1
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)

            docs = db.similarity_search("Jill")
            assert len(docs) == 2
            assert docs[0].page_content == msg2
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file2)


@wrap_test_forked
def test_zip_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            msg1 = "Hello World"
            test_file1 = os.path.join(tmp_user_path, 'test.txt')
            with open(test_file1, "wt") as f:
                f.write(msg1)
            zip_file = './tmpdata/data.zip'
            zip_data(tmp_user_path, zip_file=zip_file, fail_any_exception=True)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("World")
            assert len(docs) == 1
            assert docs[0].page_content == msg1
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_url_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        url = 'https://h2o.ai/company/team/leadership-team/'
        db = make_db_main(persist_directory=tmp_persistent_directory, url=url, fail_any_exception=True)
        assert db is not None
        docs = db.similarity_search("list founding team of h2o.ai")
        assert len(docs) == 4
        assert 'Sri Ambati' in docs[0].page_content


@wrap_test_forked
def test_html_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            html_content = """
<!DOCTYPE html>
<html>
<body>

<h1>Yugu is a wonderful place</h1>

<p>Animals love to run in the world of Yugu.  They play all day long in the alien sun.</p>

</body>
</html>
"""
            test_file1 = os.path.join(tmp_user_path, 'test.html')
            with open(test_file1, "wt") as f:
                f.write(html_content)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("Yugu")
            assert len(docs) == 1
            assert 'Yugu' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_docx_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            url = 'https://calibre-ebook.com/downloads/demos/demo.docx'
            test_file1 = os.path.join(tmp_user_path, 'demo.docx')
            download_simple(url, dest=test_file1)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("What is calibre DOCX plugin do?")
            assert len(docs) == 4
            assert 'calibre' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_md_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            test_file1 = 'README.md'
            if not os.path.isfile(test_file1):
                # see if ran from tests directory
                test_file1 = '../README.md'
                test_file1 = os.path.abspath(test_file1)
            shutil.copy(test_file1, tmp_user_path)
            test_file1 = os.path.join(tmp_user_path, os.path.basename(test_file1))
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("What is h2oGPT?")
            assert len(docs) == 4
            assert 'h2oGPT is a large language model' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_eml_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            url = 'https://raw.githubusercontent.com/FlexConfirmMail/Thunderbird/master/sample.eml'
            test_file1 = os.path.join(tmp_user_path, 'sample.eml')
            download_simple(url, dest=test_file1)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("What is subject?")
            assert len(docs) == 1
            assert 'testtest' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_simple_eml_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            html_content = """
Date: Sun, 1 Apr 2012 14:25:25 -0600
From: file@fyicenter.com
Subject: Welcome
To: someone@somewhere.com

Dear Friend,

Welcome to file.fyicenter.com!

Sincerely,
FYIcenter.com Team"""
            test_file1 = os.path.join(tmp_user_path, 'test.eml')
            with open(test_file1, "wt") as f:
                f.write(html_content)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("Subject")
            assert len(docs) == 1
            assert 'Welcome' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_odt_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            url = 'https://github.com/owncloud/example-files/raw/master/Documents/Example.odt'
            test_file1 = os.path.join(tmp_user_path, 'sample.odt')
            download_simple(url, dest=test_file1)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("What is ownCloud?")
            assert len(docs) == 4
            assert 'ownCloud' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_pptx_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            url = 'https://www.unm.edu/~unmvclib/powerpoint/pptexamples.ppt'
            test_file1 = os.path.join(tmp_user_path, 'sample.pptx')
            download_simple(url, dest=test_file1)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("Suggestions")
            assert len(docs) == 4
            assert 'Presentation' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_simple_pptx_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            url = 'https://www.suu.edu/webservices/styleguide/example-files/example.pptx'
            test_file1 = os.path.join(tmp_user_path, 'sample.pptx')
            download_simple(url, dest=test_file1)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("Example")
            assert len(docs) == 1
            assert 'Powerpoint' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_epub_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            url = 'https://contentserver.adobe.com/store/books/GeographyofBliss_oneChapter.epub'
            test_file1 = os.path.join(tmp_user_path, 'sample.epub')
            download_simple(url, dest=test_file1)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("Grump")
            assert len(docs) == 4
            assert 'happy' in docs[0].page_content or 'happiness' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@pytest.mark.skip(reason="Not supported, GPL3, and msg-extractor code fails too often")
@pytest.mark.xfail(strict=False,
                   reason="fails with AttributeError: 'Message' object has no attribute '_MSGFile__stringEncoding'. Did you mean: '_MSGFile__overrideEncoding'? even though can use online converter to .eml fine.")
@wrap_test_forked
def test_msg_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            url = 'http://file.fyicenter.com/b/sample.msg'
            test_file1 = os.path.join(tmp_user_path, 'sample.msg')
            download_simple(url, dest=test_file1)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("Grump")
            assert len(docs) == 4
            assert 'Happy' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_png_add():
    return run_png_add(captions_model=None, caption_gpu=False)


@pytest.mark.skipif(not have_gpus, reason="requires GPUs to run")
@wrap_test_forked
def test_png_add_gpu():
    return run_png_add(captions_model=None, caption_gpu=True)


@pytest.mark.skipif(not have_gpus, reason="requires GPUs to run")
@wrap_test_forked
def test_png_add_gpu_preload():
    return run_png_add(captions_model=None, caption_gpu=True, pre_load_caption_model=True)


@pytest.mark.skipif(not (have_gpus and mem_gpus[0] > 20 * 1024 ** 3), reason="requires GPUs and enough memory to run")
@wrap_test_forked
def test_png_add_gpu_blip2():
    return run_png_add(captions_model='Salesforce/blip2-flan-t5-xl', caption_gpu=True)


def run_png_add(captions_model=None, caption_gpu=False, pre_load_caption_model=False):
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            test_file1 = 'data/pexels-evg-kowalievska-1170986_small.jpg'
            if not os.path.isfile(test_file1):
                # see if ran from tests directory
                test_file1 = '../data/pexels-evg-kowalievska-1170986_small.jpg'
                assert os.path.isfile(test_file1)
            test_file1 = os.path.abspath(test_file1)
            shutil.copy(test_file1, tmp_user_path)
            test_file1 = os.path.join(tmp_user_path, os.path.basename(test_file1))
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True, enable_ocr=False, caption_gpu=caption_gpu,
                              pre_load_caption_model=pre_load_caption_model,
                              captions_model=captions_model)
            assert db is not None
            docs = db.similarity_search("cat")
            assert len(docs) == 1
            assert 'a cat sitting on a window' in docs[0].page_content
            assert os.path.normpath(docs[0].metadata['source']) == os.path.normpath(test_file1)


@wrap_test_forked
def test_simple_rtf_add():
    from make_db import make_db_main
    with tempfile.TemporaryDirectory() as tmp_persistent_directory:
        with tempfile.TemporaryDirectory() as tmp_user_path:
            rtf_content = """
{\rtf1\mac\deff2 {\fonttbl{\f0\fswiss Chicago;}{\f2\froman New York;}{\f3\fswiss Geneva;}{\f4\fmodern Monaco;}{\f11\fnil Cairo;}{\f13\fnil Zapf Dingbats;}{\f16\fnil Palatino;}{\f18\fnil Zapf Chancery;}{\f20\froman Times;}{\f21\fswiss Helvetica;}
{\f22\fmodern Courier;}{\f23\ftech Symbol;}{\f24\fnil Mobile;}{\f100\fnil FoxFont;}{\f107\fnil MathMeteor;}{\f164\fnil Futura;}{\f1024\fnil American Heritage;}{\f2001\fnil Arial;}{\f2005\fnil Courier New;}{\f2010\fnil Times New Roman;}
{\f2011\fnil Wingdings;}{\f2515\fnil MT Extra;}{\f3409\fnil FoxPrint;}{\f11132\fnil InsigniaLQmono;}{\f11133\fnil InsigniaLQprop;}{\f14974\fnil LB Helvetica Black;}{\f14976\fnil L Helvetica Light;}}{\colortbl\red0\green0\blue0;\red0\green0\blue255;
\red0\green255\blue255;\red0\green255\blue0;\red255\green0\blue255;\red255\green0\blue0;\red255\green255\blue0;\red255\green255\blue255;}{\stylesheet{\f4\fs18 \sbasedon222\snext0 Normal;}}{\info{\title samplepostscript.msw}{\author 
Computer Science Department}}\widowctrl\ftnbj \sectd \sbknone\linemod0\linex0\cols1\endnhere \pard\plain \qc \f4\fs18 {\plain \b\f21 Sample Rich Text Format Document\par 
}\pard {\plain \f20 \par 
}\pard \ri-80\sl-720\keep\keepn\absw570 {\caps\f20\fs92\dn6 T}{\plain \f20 \par 
}\pard \qj {\plain \f20 his is a sample rich text format (RTF), document. This document was created using Microsoft Word and then printing the document to a RTF file. It illustrates the very basic text formatting effects that can be achieved using RTF. 
\par 
\par 
}\pard \qj\li1440\ri1440\box\brdrs \shading1000 {\plain \f20 RTF }{\plain \b\f20 contains codes for producing advanced editing effects. Such as this indented, boxed, grayed background, entirely boldfaced paragraph.\par 
}\pard \qj {\plain \f20 \par 
Microsoft  Word developed RTF for document transportability and gives a user access to the complete set of the effects that can be achieved using RTF. \par 
}}
"""
            test_file1 = os.path.join(tmp_user_path, 'test.rtf')
            with open(test_file1, "wt") as f:
                f.write(rtf_content)
            db = make_db_main(persist_directory=tmp_persistent_directory, user_path=tmp_user_path,
                              fail_any_exception=True)
            assert db is not None
            docs = db.similarity_search("How was this document created?")
            assert len(docs) == 4
            assert 'Microsoft' in docs[1].page_content
            assert os.path.normpath(docs[1].metadata['source']) == os.path.normpath(test_file1)


if __name__ == '__main__':
    pass

"""Fetch only the three authorized small public Dryad files, preserving bytes."""
from pathlib import Path
import datetime, hashlib, json, urllib.request, urllib.error, http.cookiejar, re, html

BASE = Path(__file__).resolve().parent
FILES = {'3A.csv': 3804657, '3B.csv': 3804664, 'README.md': 3804684}

def main():
    data = BASE / 'data'
    data.mkdir(exist_ok=True)
    receipt = {'dataset_doi': '10.5061/dryad.xd2547drh',
               'dataset_version_date': '2025-01-22',
               'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'files': []}
    meta_url = 'https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.xd2547drh'
    metadata = json.load(urllib.request.urlopen(meta_url, timeout=30))
    receipt['metadata_url'] = meta_url
    receipt['metadata'] = {k:metadata[k] for k in ['title','versionNumber','publicationDate','lastModificationDate','license','relatedWorks']}
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    page_url = 'https://datadryad.org/dataset/doi:10.5061/dryad.xd2547drh'
    page = opener.open(page_url, timeout=20).read().decode()
    token = re.search(r'<meta name="csrf-token" content="([^"]+)"',page).group(1)
    headers = {'X-Requested-With':'XMLHttpRequest','X-CSRF-Token':token,'Referer':page_url}
    for name, identifier in FILES.items():
        target = data / name
        if target.exists():
            raise FileExistsError(target)
        file_meta_url = f'https://datadryad.org/api/v2/files/{identifier}'
        file_meta = json.load(urllib.request.urlopen(file_meta_url, timeout=30))
        if file_meta['path'] != name:
            raise ValueError('Unexpected source filename')
        url = 'https://datadryad.org' + file_meta['_links']['stash:download']['href']
        method = 'direct_public_download'
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                content = response.read(20001)
                content_type = response.headers.get('Content-Type', '')
        except urllib.error.HTTPError as error:
            if name == 'README.md':
                receipt['files'].append({'name':name,'retrieved':False,'reason':f'API download HTTP {error.code}; public file_stream HTTP 403; preview unavailable',
                                         'repository_metadata':file_meta,'definitions_read_from':page_url})
                continue
            url = f'https://datadryad.org/data_file/preview/{identifier}'
            preview = opener.open(urllib.request.Request(url,headers=headers),timeout=20).read().decode()
            rows = re.findall(r'<tr>(.*?)</tr>',preview,re.S)
            content = b'\xef\xbb\xbf' + ''.join(','.join(html.unescape(x) for x in re.findall(r'<t[hd]>(.*?)</t[hd]>',row,re.S))+'\n' for row in rows).encode()
            content_type = 'text/csv'
            method = 'lossless_public_preview_reconstruction_verified_against_repository_sha256'
        if len(content) > 20000 or b'<html' in content.lower():
            raise ValueError('Unexpected data response')
        content.decode('utf-8-sig')
        if len(content) != file_meta['size'] or hashlib.sha256(content).hexdigest() != file_meta['digest']:
            raise ValueError('Repository checksum or byte count mismatch')
        target.write_bytes(content)
        receipt['files'].append({'name':name,'url':url,'bytes':len(content),
                                'content_type':content_type, 'repository_digest_matches':True,
                                'metadata_url':file_meta_url,'retrieval_method':method,
                                'sha256':hashlib.sha256(content).hexdigest()})
    (BASE / 'data_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()

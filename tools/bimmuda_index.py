"""Buduje bimmuda.json – spis hitów z Billboard Melodic Music Dataset (BiMMuDa) dla katalogu w aplikacji.

BiMMuDa (Madeline Hamilton i in., TISMIR 2024): ręcznie spisane główne melodie 5 największych singli
z rocznej listy Billboard Year-End Hot 100 dla każdego roku od 1950 (w repozytorium do 2024).
Pliki leżą w repozytorium madelinehamilton/BiMMuDa (bimmuda_dataset/<rok>/<miejsce>/<rok>_<miejsce>_full.mid),
aplikacja pobiera je przez raw.githubusercontent.com (nagłówek CORS: *), adresem przypiętym do commita.

Użycie:
    git clone --depth 1 https://github.com/madelinehamilton/BiMMuDa /tmp/bimmuda
    python3 tools/bimmuda_index.py /tmp/bimmuda
"""
import csv
import json
import os
import re
import subprocess
import sys

REPO = 'madelinehamilton/BiMMuDa'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bimmuda.json')


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def main(clone):
    sha = subprocess.check_output(['git', '-C', clone, 'rev-parse', 'HEAD'], text=True).strip()
    meta = os.path.join(clone, 'metadata', 'bimmuda_per_song_metadata.csv')
    songs, seen, missing = [], set(), []
    with open(meta, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            # miejsce bywa z literą (np. „2a”, „2b” – singiel z dwiema stronami A)
            year, pos = int(row['Year']), row['Position'].strip()
            title, artist = row['Title'].strip(), row['Artist'].strip()
            path = 'bimmuda_dataset/%d/%s/%d_%s_full.mid' % (year, pos, year, pos.zfill(2 + (not pos.isdigit())))
            if not os.path.exists(os.path.join(clone, path)):
                missing.append('%d/%s %s – %s' % (year, pos, artist, title))
                continue
            key = (norm(title), norm(artist))
            if key in seen:  # ten sam utwór w dwóch latach (np. Blinding Lights 2020 i 2021)
                continue
            seen.add(key)
            # [tytuł, wykonawca, rok, ścieżka pliku od bimmuda_dataset/]
            songs.append([title, artist, year, path[len('bimmuda_dataset/'):]])
    data = {'repo': REPO, 'sha': sha, 'n': len(songs), 's': songs}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{OUT}: {len(songs)} utworów, commit {sha}, {os.path.getsize(OUT) // 1024} KB')
    if missing:
        print('bez pliku z melodią:', '; '.join(missing))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/bimmuda')

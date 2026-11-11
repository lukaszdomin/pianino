"""Buduje lakh.json – spis piosenek z Lakh MIDI Dataset (zbiór „clean”) dla katalogu w aplikacji.

Pliki leżą w repozytorium imsparsh/Lakh-MIDI-Dataset-Clean na GitHubie (Wykonawca/Tytuł.mid),
a aplikacja pobiera je przez raw.githubusercontent.com (nagłówek CORS: *). Sam spis trzymamy u nas,
bo GitHub nie ma wyszukiwarki z CORS. Adresy są przypięte do jednego commita (SHA), więc zmiany
w tamtym repozytorium niczego nam nie zepsują.

Użycie (bez pobierania samych plików MIDI, tylko lista nazw):
    git clone --filter=blob:none --no-checkout --depth 1 https://github.com/imsparsh/Lakh-MIDI-Dataset-Clean /tmp/lakh
    python3 tools/lakh_index.py /tmp/lakh
Uwaga: nie używaj `git ls-tree -l` – przy --filter=blob:none pobiera każdy plik po kolei.
"""
import json
import os
import subprocess
import sys

REPO = 'imsparsh/Lakh-MIDI-Dataset-Clean'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lakh.json')


def main(clone):
    sha = subprocess.check_output(['git', '-C', clone, 'rev-parse', 'HEAD'], text=True).strip()
    names = subprocess.check_output(['git', '-C', clone, '-c', 'core.quotepath=off', 'ls-tree', '-r', '--name-only', 'HEAD'],
                                    text=True).splitlines()
    artists = {}
    for path in names:
        parts = path.split('/')
        if len(parts) != 2 or not parts[1].lower().endswith('.mid'):
            continue
        artists.setdefault(parts[0], []).append(parts[1][:-4])
    data = {
        'repo': REPO,
        'sha': sha,
        'n': sum(len(v) for v in artists.values()),
        # [wykonawca, [tytuły bez .mid]] – nazwy dokładnie jak w repozytorium (z podkreśleniami),
        # żeby dało się z nich odtworzyć ścieżkę pliku
        'a': [[a, sorted(t)] for a, t in sorted(artists.items(), key=lambda x: x[0].lower())],
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{OUT}: {len(artists)} wykonawców, {data["n"]} plików, commit {sha}, {os.path.getsize(OUT) // 1024} KB')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/lakh')

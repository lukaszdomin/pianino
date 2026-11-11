"""Szybki test aplikacji z zasymulowanym keyboardem (bez prawdziwego sprzętu).

Uruchomienie:  python3 tests/smoke_test.py
Wymaga: playwright (pip install playwright) i przeglądarki Chrome/Chromium.
Symuluje starą implementację Web MIDI jak w Web MIDI Browser (tylko forEach,
port „Bluetooth Session 1”, zdarzenia przez onmidimessage i addEventListener).
"""
import asyncio
import os
import shutil
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def serve():
    """Lokalny serwer HTTP z folderem aplikacji (jak GitHub Pages), żeby działał fetch('lakh.json')."""
    import functools
    import http.server
    import threading

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return 'http://127.0.0.1:%d/index.html' % srv.server_address[1]

MOCK = """
window.__sent = [];
class In extends EventTarget {
  constructor() { super(); this.id = 'bt1'; this.name = 'Bluetooth Session 1'; this.onmidimessage = null; }
  fire(d) { const ev = new Event('midimessage'); ev.data = new Uint8Array(d);
            if (this.onmidimessage) this.onmidimessage(ev); this.dispatchEvent(ev); }
}
const i = new In(); window.__in = i;
const o = {id: 'bt1', name: 'Bluetooth Session 1', send: b => window.__sent.push(Array.from(b))};
navigator.requestMIDIAccess = async () => ({sysexEnabled: true,
  outputs: {forEach: cb => cb(o, o.id)}, inputs: {forEach: cb => cb(i, i.id)}});
"""


import json
import struct

# Najmniejszy poprawny plik MIDI: jedna nuta C4
TINY_MIDI = (b'MThd' + struct.pack('>IHHH', 6, 0, 1, 96) +
             b'MTrk' + struct.pack('>I', 12) + bytes([0x00, 0x90, 60, 100, 0x60, 0x80, 60, 0, 0x00, 0xFF, 0x2F, 0x00]))


def hard_midi():
    """Gęsty plik: 4-dźwiękowe akordy co 1/16 s na całej klawiaturze → poziom „Trudne”."""
    ev = b''
    for i in range(160):
        chord = [36 + (i * 7) % 24, 52 + (i * 5) % 20, 72 + (i * 3) % 12, 84 + (i * 11) % 12]
        for n in chord:
            ev += bytes([0x00, 0x90, n, 90])
        for k, n in enumerate(chord):
            ev += bytes([12 if k == 0 else 0x00, 0x80, n, 0])
    ev += bytes([0x00, 0xFF, 0x2F, 0x00])
    return b'MThd' + struct.pack('>IHHH', 6, 0, 1, 96) + b'MTrk' + struct.pack('>I', len(ev)) + ev


HARD_MIDI = hard_midi()


def track(name, prog, ch, notes, step):
    """Ścieżka MIDI: nazwa, program (instrument), kanał, lista nut lub akordów, odstęp w tickach."""
    nm = name.encode()
    ev = bytes([0x00, 0xFF, 0x03, len(nm)]) + nm + bytes([0x00, 0xC0 | ch, prog])
    for item in notes:
        chord = item if isinstance(item, (list, tuple)) else [item]
        for n in chord:
            ev += bytes([0x00, 0x90 | ch, n, 90])
        for k, n in enumerate(chord):
            ev += bytes([step if k == 0 else 0x00, 0x80 | ch, n, 0])
    ev += bytes([0x00, 0xFF, 0x2F, 0x00])
    return b'MTrk' + struct.pack('>I', len(ev)) + ev


def song_midi(*tracks):
    return b'MThd' + struct.pack('>IHHH', 6, 1, len(tracks), 96) + b''.join(tracks)


# Piosenka: bas (nisko), pad (akordy), melodia na „Lead 2 (sawtooth)” wysoko – ścieżka bez nazwy „Melody”
POP_MIDI = song_midi(
    track('Bass', 33, 1, [36, 43, 41, 38] * 12, 96),
    track('Pad', 89, 2, [[60, 64, 67], [57, 60, 64]] * 12, 192),
    track('Synth', 81, 3, [72, 74, 76, 79, 76, 74, 72, 71] * 6, 96),
)
# Fortepian na dwie ręce: obie ścieżki zostają zaznaczone
PIANO_MIDI = song_midi(
    track('Right', 0, 0, [72, 74, 76, 77] * 6, 96),
    track('Left', 0, 0, [48, 55] * 12, 96),
)
HITS = {'commons': 0, 'bitmidi': 0, 'lakh': 0}
CORS = {'Access-Control-Allow-Origin': '*'}
COMMONS_JSON = {'query': {'pages': {'111': {'pageid': 111, 'index': 1, 'title': 'File:Chopin-nocturne-test.mid',
    'imageinfo': [{'url': 'https://upload.wikimedia.org/x/Chopin-nocturne-test.mid?utm=1', 'size': 1234,
                   'duration': 95, 'descriptionurl': 'https://commons.wikimedia.org/wiki/File:x'}]}}}}
BITMIDI_JSON = {'result': {'pageTotal': 1, 'results': [
    {'id': 222, 'name': 'Chopin_Waltz_Test.mid', 'downloadUrl': '/uploads/222.mid', 'url': '/x', 'plays': 1500}]}}


async def mock_catalog(page, bitmidi_ok=True):
    async def commons(route):
        await route.fulfill(status=200, headers=CORS, content_type='application/json', body=json.dumps(COMMONS_JSON))

    async def bitmidi(route):
        if bitmidi_ok:
            await route.fulfill(status=200, headers=CORS, content_type='application/json', body=json.dumps(BITMIDI_JSON))
        else:
            await route.fulfill(status=500, headers=CORS, body='err')

    async def midi(route):
        HITS['commons'] += 1
        await route.fulfill(status=200, headers=CORS, content_type='audio/midi', body=TINY_MIDI)

    async def midi_hard(route):
        HITS['bitmidi'] += 1
        await route.fulfill(status=200, headers=CORS, content_type='audio/midi', body=HARD_MIDI)

    await page.unroute('**/*')
    await page.route('https://commons.wikimedia.org/**', commons)
    await page.route('https://bitmidi.com/api/**', bitmidi)
    await page.route('https://upload.wikimedia.org/**', midi)
    await page.route('https://bitmidi.com/uploads/**', midi_hard)

    async def midi_pop(route):
        HITS['lakh'] += 1
        await route.fulfill(status=200, headers=CORS, content_type='audio/midi', body=POP_MIDI)
    await page.route('https://raw.githubusercontent.com/**', midi_pop)


async def add_song(page, data, title, src=None, select=True):
    """Dodaje plik MIDI do „Moje utwory” tak jak Katalog (ręczne wgrywanie zostało usunięte)."""
    await page.evaluate("""([b, t, s, sel]) => { const p = addUserSong(new Uint8Array(b).buffer, t, s || undefined);
                           if (sel) selectSong(p); }""", [list(data), title, src, select])


LIB_TITLES = ['ABBA – Dancing Queen', 'Haddaway – What Is Love', 'Madonna – La Isla Bonita', 'Toto – Africa',
              'Darude – Sandstorm', 'Daft Punk – One More Time', 'Corona – The Rhythm of the Night',
              '2 Unlimited – No Limit', 'Eiffel 65 – Blue (Da Ba Dee)', 'Chopin – Nocturne Op. 9 No. 2 in E-flat major',
              'Für Elise full version', 'Satie – Gymnopédie No. 1']


async def library_tests(page, check):
    """Lewy panel: lista widoczna w poziomie, zwijane wbudowane, dwie linie, Edytuj/Usuń, szukanie i filtr poziomu."""
    for k, t in enumerate(LIB_TITLES):
        src = ('lakh:x/%d' % k) if k < 9 else ('bitmidi:%d' % k) if k < 11 else None
        await add_song(page, TINY_MIDI, t, src, select=False)
    await page.evaluate("userSongs.forEach((u, i) => u.lvl = [1, 2, 3][i % 3]); saveUser(); renderLib()")
    rows = await page.eval_on_selector_all('#lib .song', 'els => els.map(e => e.querySelector(".tt").textContent)')
    check(len(rows) == 12 and rows[0] == 'Satie – Gymnopédie No. 1',
          'Moje utwory: wszystkie, najnowsze na górze ' + str(rows[:2]))
    box = await page.evaluate("""() => { const sc = document.querySelector('#libScroll').getBoundingClientRect();
        const r = [...document.querySelectorAll('#lib .song')].filter(e => { const b = e.getBoundingClientRect(); return b.top >= sc.top && b.bottom <= sc.bottom; });
        return {h: sc.height, visible: r.length}; }""")
    check(box['visible'] >= 5, 'w poziomie (1180×820) widać co najmniej 5 pobranych utworów ' + str(box))
    check(await page.evaluate("document.querySelector('#libBuiltin').hidden"), 'wbudowane zwinięte, gdy są pobrane utwory')
    await page.click('#builtinToggle')
    check(not await page.evaluate("document.querySelector('#libBuiltin').hidden") and await page.evaluate("S.builtinOpen") is True,
          'wbudowane można rozwinąć (zapamiętane)')
    await page.click('#builtinToggle')
    abba = await page.evaluate("""() => { const r = [...document.querySelectorAll('#lib .song')].find(e => e.querySelector('.tt').textContent === 'Dancing Queen');
        return r ? r.querySelector('.sub').textContent : null; }""")
    check(abba is not None and 'ABBA' in abba and 'Lakh' in abba and 'Łatwe' in abba, 'Lakh: tytuł w 1. linii, wykonawca·poziom·źródło w 2. ' + str(abba))
    own = await page.evaluate("document.querySelector('#lib .song .sub').textContent")
    check('własny plik' in own, 'plik bez źródła opisany jako „własny plik” ' + own)
    check(await page.eval_on_selector_all('#lib .del', 'e => e.length') == 0, 'bez „Edytuj” nie ma przycisków usuwania')

    # wyszukiwanie i filtr poziomu (od 10 utworów)
    check(not await page.evaluate("document.querySelector('#libTools').hidden"), 'przy 12 utworach jest wyszukiwanie i filtr')
    await page.fill('#libQ', 'abba')
    check(await page.eval_on_selector_all('#lib .song', 'e => e.length') == 1, 'szukanie „abba” zostawia 1 utwór')
    await page.fill('#libQ', 'gymnopedie')
    check(await page.eval_on_selector_all('#lib .song', 'e => e.length') == 1, 'szukanie bez polskich/obcych znaków')
    await page.fill('#libQ', 'xyzxyz')
    check('Żaden utwór nie pasuje' in await page.text_content('#lib'), 'komunikat, gdy nic nie pasuje')
    await page.fill('#libQ', '')
    await page.click('#libLvlSeg >> text=Trudne')
    lv = await page.eval_on_selector_all('#lib .song .lvl', 'els => els.map(e => e.textContent)')
    check(len(lv) == 4 and set(lv) == {'Trudne'}, 'filtr poziomu „Trudne” ' + str(lv))
    await page.click('#libLvlSeg >> text=Każdy')

    # Edytuj → Usuń
    await page.click('#libEdit')
    check(await page.eval_on_selector_all('#lib .del', 'e => e.length') == 12 and await page.text_content('#libEdit') == 'Gotowe',
          '„Edytuj” pokazuje „Usuń” przy każdym utworze')
    await page.click('#lib .song >> nth=1')
    check(await page.evaluate("!song || song.title !== 'Für Elise full version'"), 'w trybie edycji stuknięcie nie otwiera utworu')
    for _ in range(3):
        await page.click('#lib .song >> nth=0 >> .del')
    check(await page.evaluate("userSongs.length") == 9, 'usuwanie działa')
    check(await page.evaluate("document.querySelector('#libTools').hidden"), 'poniżej 10 utworów wyszukiwanie znika')
    await page.click('#libEdit')
    check(await page.eval_on_selector_all('#lib .del', 'e => e.length') == 0, '„Gotowe” chowa przyciski usuwania')
    await page.evaluate("userSongs.length = 0; saveUser(); S.builtinOpen = null; renderLib()")
    check(not await page.evaluate("document.querySelector('#libBuiltin').hidden") and 'Katalog' in await page.text_content('#lib'),
          'pusta lista: wbudowane rozwinięte, podpowiedź o Katalogu')


def chrome_path():
    for name in ('google-chrome', 'chromium', 'chromium-browser'):
        p = shutil.which(name)
        if p:
            return p
    return None


async def main():
    failures = []

    def check(cond, msg):
        print(('OK   ' if cond else 'BŁĄD ') + msg)
        if not cond:
            failures.append(msg)

    async with async_playwright() as p:
        exe = chrome_path()
        browser = await p.chromium.launch(executable_path=exe, args=['--no-sandbox']) if exe \
            else await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1180, 'height': 820})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.add_init_script(MOCK)
        await page.goto(serve())
        await page.wait_for_timeout(400)

        check('Bluetooth Session 1' in await page.text_content('#status'), 'wykrywa keyboard')
        lib = await page.eval_on_selector_all('#libBuiltin .song', 'els => els.map(e => e.textContent)')
        check('Wlazł kotek na płotekŁatwe' in lib and 'Dla Elizy – początekŚrednie' in lib, 'wbudowane utwory mają poziom ' + str(lib))

        # Tryb „Czekaj na mnie”: Oda do radości zaczyna się od E4 (MIDI 64 -> światło 43)
        await page.click('text=Oda do radości – Beethoven')
        await page.click('#playBtn')
        await page.wait_for_timeout(100)
        sent = await page.evaluate('__sent')
        check([0xA2, 43, 1] in sent, 'zapala pierwszy klawisz (A2 2b 01)')
        await page.evaluate('__in.fire([0x90,64,90]); __in.fire([0x80,64,0])')
        await page.wait_for_timeout(150)
        check('krok 2' in await page.text_content('#posTxt'), 'po trafieniu przechodzi do kroku 2')
        await page.evaluate('__in.fire([0x90,61,90])')
        check('✗ 1' in await page.text_content('#stats'), 'liczy pomyłkę')

        # Cały utwór na dwie ręce (akordy)
        await page.click('text=Gama C-dur (obie ręce)')
        await page.click('#playBtn')
        for _ in range(20):
            st = await page.evaluate('steps[stepIdx] ? steps[stepIdx].notes : null')
            if not st:
                break
            for n in st:
                await page.evaluate(f'__in.fire([0x90,{n},90])')
        await page.wait_for_timeout(100)
        check(await page.evaluate("document.querySelector('#result').classList.contains('open')"),
              'kończy utwór i pokazuje wynik')
        await page.click('#closeRes')

        # Wybór ścieżek: piosenka → tylko melodia (⭐) z nazwą instrumentu; fortepian → obie ręce
        check(await page.query_selector('#file') is None and await page.query_selector('.addfile') is None,
              'nie ma już ręcznego dodawania plików MIDI')
        await add_song(page, POP_MIDI, 'Piosenka')
        await page.wait_for_function("song && song.title === 'Piosenka'")
        chips = await page.eval_on_selector_all('#tracks .chip', 'els => els.map(e => [e.textContent, e.classList.contains("on")])')
        on = [c[0] for c in chips if c[1]]
        check(len(chips) == 3 and len(on) == 1 and on[0].startswith('⭐ Synth'), 'piosenka: zaznaczona tylko melodia ' + str(chips))
        check('Lead 2 (sawtooth)' in on[0] and any('Electric Bass (finger)' in c[0] for c in chips), 'ścieżki pokazują instrument')
        check(await page.evaluate('ns.every(n => n.m >= 71)'), 'odtwarzacz dostaje tylko nuty melodii')
        await page.click('#tracks .chip >> text=Bass')
        check(await page.evaluate('sel.size') == 2, 'można dołączyć bas')
        await add_song(page, PIANO_MIDI, 'Fortepian')
        await page.wait_for_function("song && song.title === 'Fortepian'")
        check(await page.evaluate('sel.size') == 2 and await page.evaluate('song.melody') == -1, 'fortepian na dwie ręce: obie ścieżki')
        await page.evaluate("userSongs.length = 0; saveUser(); renderLib()")

        await library_tests(page, check)

        # Katalog utworów (odpowiedzi bibliotek są podstawione, bez internetu)
        await mock_catalog(page)
        await page.click('#openCatalog')
        sugg = await page.eval_on_selector_all('#catSugg .sgroup', 'els => els.map(e => e.textContent)')
        check(len(sugg) >= 3 and any('Better Off Alone' in g for g in sugg) and any('ABBA' in g for g in sugg), 'podpowiedzi pop i dance ' + str(sugg))
        await page.fill('#catQ', 'chopin testowy')  # Lakh tego nie zna, więc wyniki są tylko z podstawionych bibliotek
        await page.press('#catQ', 'Enter')
        await page.wait_for_selector('.cat', timeout=3000)
        titles = await page.eval_on_selector_all('.cat .t b', 'els => els.map(e => e.textContent)')
        check(titles == ['Chopin nocturne test', 'Chopin Waltz Test'], 'katalog pokazuje wyniki z obu bibliotek ' + str(titles))

        # Poziom trudności: liczony w tle z pobranych plików
        await page.wait_for_selector('.cat .lvl.l3', timeout=3000)
        await page.wait_for_selector('.cat .lvl.l1', timeout=3000)
        lv = await page.eval_on_selector_all('.cat .lvl', 'els => els.map(e => e.textContent)')
        check(lv == ['Łatwe', 'Trudne'], 'katalog pokazuje poziom trudności ' + str(lv))
        await page.click('#catLvlSeg >> text=Łatwe')
        titles = await page.eval_on_selector_all('.cat .t b', 'els => els.map(e => e.textContent)')
        check(titles == ['Chopin nocturne test'], 'filtr „Łatwe” ' + str(titles))
        await page.click('#catLvlSeg >> text=Trudne')
        titles = await page.eval_on_selector_all('.cat .t b', 'els => els.map(e => e.textContent)')
        check(titles == ['Chopin Waltz Test'], 'filtr „Trudne” ' + str(titles))
        await page.click('#catLvlSeg >> text=Średnie')
        check('nie ma utworów na poziomie' in await page.text_content('#catMsg'), 'pusty poziom pokazuje komunikat')
        await page.click('#catLvlSeg >> text=Każdy poziom')
        check(await page.eval_on_selector_all('.cat', 'e => e.length') == 2, '„Każdy poziom” pokazuje wszystko')
        check(await page.evaluate("JSON.parse(localStorage.getItem('sk_levels'))['bitmidi:222'].l") == 3, 'poziomy są zapamiętane')

        await page.click('.cat >> nth=0 >> text=Pobierz')
        await page.wait_for_selector('.cat >> nth=0 >> text=Mam', timeout=3000)
        check(HITS['commons'] == 1, 'pobranie nie ściąga pliku drugi raz (zapytań: %d)' % HITS['commons'])
        check(await page.evaluate("userSongs[0].lvl") == 1, 'pobrany utwór ma zapisany poziom')
        check('Łatwe' in await page.text_content('#lib'), 'poziom widać w „Moje utwory”')
        check(await page.evaluate("userSongs.some(u => u.src === 'commons:111')"), 'pobrany utwór trafia do „Moje utwory”')
        check(await page.evaluate("JSON.parse(localStorage.getItem('sk_songs')).length") == 1, 'pobrany utwór jest zapisany')
        await page.check('#catMissing')
        check(await page.eval_on_selector_all('.cat', 'e => e.length') == 1, 'filtr „tylko te, których nie mam” ukrywa pobrane')
        await page.uncheck('#catMissing')
        await page.click('.cat >> nth=0 >> text=Mam')
        check(not await page.evaluate("document.querySelector('#catalog').classList.contains('open')"), '„Mam – graj” zamyka katalog')
        check(await page.text_content('#songTitle') == 'Chopin nocturne test', '„Mam – graj” otwiera utwór')

        # Lakh: spis z lakh.json (prawdziwy plik), pliki z raw.githubusercontent.com (podstawione)
        await page.click('#openCatalog')
        await page.click('#catSrcSeg >> text=Lakh')
        await page.fill('#catQ', 'dancing queen')
        await page.press('#catQ', 'Enter')
        await page.wait_for_selector('.cat .badge.lakh', timeout=5000)
        titles = await page.eval_on_selector_all('.cat .t b', 'els => els.map(e => e.textContent)')
        check(titles[0] == 'ABBA – Dancing Queen' and 'ABBA – Dancing Queen (wersja 2)' in titles, 'Lakh znajduje piosenki ' + str(titles[:3]))
        url = await page.evaluate("cat.items[0].url")
        check(url.startswith('https://raw.githubusercontent.com/imsparsh/Lakh-MIDI-Dataset-Clean/') and url.endswith('/ABBA/Dancing_Queen.mid'), 'adres pliku Lakh ' + url)
        await page.fill('#catQ', 'beatles let it be')
        await page.press('#catQ', 'Enter')
        await page.wait_for_selector('.cat .badge.lakh', timeout=5000)
        check((await page.text_content('.cat .t b')).startswith('The Beatles – Let It Be'), 'Lakh: wykonawca + tytuł w zapytaniu')

        # Odsłuch przed pobraniem
        await page.wait_for_function("catA.active === 0 && !catA.queue.length", timeout=5000)
        HITS['lakh'] = 0
        await page.evaluate("catA.buf.clear()")
        before = await page.evaluate("userSongs.length")
        await page.click('.cat >> nth=0 >> button.pv')
        await page.wait_for_function("pv.src !== ''", timeout=3000)
        check('Stop' in await page.text_content('.cat >> nth=0 >> button.pv') or '■' in await page.text_content('.cat >> nth=0 >> button.pv'), 'odsłuch gra (przycisk Stop)')
        check(await page.evaluate("[...pv.mel].length") == 1, 'odsłuch wyróżnia melodię')
        check(await page.evaluate("!!unlockEl && !unlockEl.paused"), 'odsłuch odblokowuje dźwięk iPada (ciche <audio> gra)')
        check(await page.evaluate("actx.state") == 'running', 'AudioContext działa')
        check(await page.evaluate("userSongs.length") == before, 'odsłuch niczego nie zapisuje')
        await page.click('.cat >> nth=0 >> button.pv')
        check(await page.evaluate("pv.src") == '', 'drugie stuknięcie zatrzymuje odsłuch')
        await page.click('.cat >> nth=0 >> text=Pobierz')
        await page.wait_for_selector('.cat >> nth=0 >> text=Mam', timeout=3000)
        check(HITS['lakh'] == 1, 'po odsłuchu pobranie nie ściąga pliku drugi raz (zapytań: %d)' % HITS['lakh'])
        await page.click('.cat >> nth=0 >> button.pv')
        await page.wait_for_function("pv.src !== ''", timeout=3000)
        await page.click('#closeCatalog')
        check(await page.evaluate("pv.src") == '', 'zamknięcie katalogu zatrzymuje odsłuch')
        await page.evaluate("userSongs.length = 0; saveUser(); renderLib()")
        await page.click('#openCatalog')
        await page.click('#catSrcSeg >> text=Wszystkie')
        await page.click('#closeCatalog')

        await mock_catalog(page, bitmidi_ok=False)
        await page.click('#openCatalog')
        await page.fill('#catQ', 'nokturn')
        await page.press('#catQ', 'Enter')
        await page.wait_for_selector('#catMsg:has-text("BitMidi")', timeout=3000)
        check(await page.eval_on_selector_all('.cat', 'e => e.length') == 1, 'gdy BitMidi nie działa, wyniki z Wikimedii dalej są')
        await page.click('#closeCatalog')

        # Dziennik
        await page.click('#openSettings')
        await page.wait_for_timeout(200)
        log = await page.input_value('#logBox')
        check('WYSŁANO: a2' in log, 'dziennik zapisuje wysłane wiadomości')

        check(not errors, 'brak błędów JS ' + (str(errors) if errors else ''))
        await browser.close()

    print('\nWYNIK:', 'wszystko OK' if not failures else f'{len(failures)} błąd(y)')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    asyncio.run(main())

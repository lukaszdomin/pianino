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
HITS = {'commons': 0, 'bitmidi': 0, 'lakh': 0, 'piano': 0}


def fake_soundfont():
    """Paczka próbek w formacie midi-js-soundfonts: 88 nut A0–C8, każda to 0,3 s sinusa w WAV (zamiast MP3)."""
    import base64
    import math
    names = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    rate, n = 8000, 2400
    out = []
    for midi in range(21, 109):
        f = 440 * 2 ** ((midi - 69) / 12)
        pcm = b''.join(struct.pack('<h', int(3000 * math.sin(2 * math.pi * f * i / rate))) for i in range(n))
        wav = (b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) +
               b'data' + struct.pack('<I', len(pcm)) + pcm)
        out.append('"%s%d": "data:audio/wav;base64,%s"' % (names[midi % 12], midi // 12 - 1, base64.b64encode(wav).decode()))
    return ("if (typeof(MIDI) === 'undefined') var MIDI = {};\nMIDI.Soundfont.acoustic_grand_piano = {\n" + ',\n'.join(out) + '\n}').encode()


SOUNDFONT = fake_soundfont()


async def route_piano(page):
    async def piano(route):
        HITS['piano'] += 1
        await route.fulfill(status=200, headers=CORS, content_type='text/javascript', body=SOUNDFONT)
    await page.route('https://raw.githubusercontent.com/gleitz/**', piano)
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
    await route_piano(page)  # zarejestrowane później = ma pierwszeństwo przed midi_pop


async def add_song(page, data, title, src=None, select=True):
    """Dodaje plik MIDI do „Moje utwory” tak jak Katalog (ręczne wgrywanie zostało usunięte)."""
    await page.evaluate("""([b, t, s, sel]) => { const p = addUserSong(new Uint8Array(b).buffer, t, s || undefined);
                           if (sel) selectSong(p); }""", [list(data), title, src, select])


LIB_TITLES = ['ABBA – Dancing Queen', 'Haddaway – What Is Love', 'Madonna – La Isla Bonita', 'Toto – Africa',
              'Darude – Sandstorm', 'Daft Punk – One More Time', 'Corona – The Rhythm of the Night',
              '2 Unlimited – No Limit', 'Eiffel 65 – Blue (Da Ba Dee)', 'Chopin – Nocturne Op. 9 No. 2 in E-flat major',
              'Für Elise full version', 'Satie – Gymnopédie No. 1']


COUNT_PX = """([r, g, b]) => {
  const cv = document.querySelector('#viewCv');
  const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data; let n = 0;
  for (let i = 0; i < d.length; i += 4)
    if (d[i + 3] > 200 && Math.abs(d[i] - r) < 12 && Math.abs(d[i + 1] - g) < 12 && Math.abs(d[i + 2] - b) < 12) n++;
  return n;
}"""
ORANGE, LIGHT_ORANGE, RED, GREEN = [255, 159, 28], [255, 194, 102], [229, 72, 77], [46, 194, 126]


async def opt(page, selector):
    """Kliknięcie w menu „Opcje” (tryb, tempo, transpozycja, dźwięk, widok) – otwiera je, gdy jest zamknięte."""
    if await page.evaluate("document.querySelector('#opts').hidden"):
        await page.click('#optsBtn')
    await page.click(selector)


async def options_menu_tests(page, check):
    """Pasek odtwarzacza: na wierzchu tylko Start/cofnij/dalej/od początku/suwak, reszta w menu „Opcje”."""
    check(not await page.is_visible('#modeSeg') and not await page.is_visible('#speed') and not await page.is_visible('#viewSeg'),
          'tryb, tempo i widok schowane w menu „Opcje”')
    for sel in ('#playBtn', '#restartBtn', '#prevBtn', '#nextBtn', '#pos', '#optsBtn'):
        check(await page.is_visible(sel), 'na wierzchu: ' + sel)
    await page.click('#optsBtn')
    check(await page.is_visible('#modeSeg') and await page.is_visible('#speed') and await page.is_visible('#trUp')
          and await page.is_visible('#sound') and await page.is_visible('#viewSeg'), 'menu „Opcje” pokazuje wszystkie opcje')
    sum0 = await page.text_content('#optsSum')
    await page.click('#trUp')
    check('+1' in await page.text_content('#optsSum'), 'podsumowanie na przycisku pokazuje transpozycję (%s)' % await page.text_content('#optsSum'))
    await page.click('#trDown')
    check(await page.text_content('#optsSum') == sum0, 'transpozycja wraca do 0')
    await page.mouse.click(700, 160)  # stuknięcie obok menu
    check(not await page.is_visible('#opts'), 'stuknięcie obok zamyka menu')
    # w poziomie z pięciolinią mieści się pole „Zagraj” (bez przewijania)
    fits = await page.evaluate("""() => { const n = document.querySelector('#now').getBoundingClientRect(),
        p = document.querySelector('#player').getBoundingClientRect(); return n.bottom <= p.bottom + 1; }""")
    check(fits, 'w poziomie (1180×820) z nutami pole „Zagraj” mieści się bez przewijania')


async def view_tests(page, check):
    """Widok nut nad klawiaturą: pięciolinia, wodospad, wyłączony. Oda do radości gra, krok 2, Cis4 wciśnięte jako pomyłka."""
    px = lambda col: page.evaluate(COUNT_PX, col)
    check(await page.evaluate("S.view") == 'staff' and await page.is_visible('#viewCv'), 'domyślnie widać pięciolinię')
    check(await page.evaluate("document.querySelector('#viewCv').width > 0"), 'pięciolinia ma rozmiar')
    await page.wait_for_timeout(300)
    check(await px(ORANGE) > 30, 'pięciolinia: aktualna nuta na pomarańczowo')
    check(await px(RED) > 30, 'pięciolinia: pomyłka (trzymany klawisz) na czerwono')
    await page.evaluate('__in.fire([0x80,61,0])')
    await page.wait_for_timeout(100)
    check(await px(RED) == 0, 'po puszczeniu klawisza czerwona nuta znika')
    st = await page.evaluate('steps[stepIdx].notes')
    pos_before = await page.evaluate('vw.pos')
    for n in st:
        await page.evaluate(f'__in.fire([0x90,{n},90]); __in.fire([0x80,{n},0])')
    await page.wait_for_timeout(500)
    check(await page.evaluate('vw.pos') == pos_before + 1, 'po trafieniu pięciolinia przesuwa się o krok')

    await opt(page, '#viewSeg >> text=Wodospad')
    await page.wait_for_timeout(200)
    check(await page.evaluate("JSON.parse(localStorage.getItem('sk_settings')).view") == 'fall', 'wybór widoku zapamiętany')
    check(await page.evaluate("document.querySelector('#view').className") == 'fall', 'wodospad włączony')
    check(await px(LIGHT_ORANGE) > 30, 'wodospad: nuta do zagrania przy klawiaturze')
    n0 = (await page.evaluate('steps[stepIdx].notes'))[0]
    check(await page.evaluate(f"""(() => {{ const g = kGeom.get({n0}), cv = document.querySelector('#viewCv');
        const x = Math.round((g.l + g.w / 2) * cv.width), d = cv.getContext('2d').getImageData(x, cv.height - 12, 1, 1).data;
        return d[0] > 240 && d[1] > 180 && d[2] > 80; }})()"""), 'wodospad: pasek stoi nad właściwym klawiszem')
    await page.evaluate('__in.fire([0x90,37,90])')
    await page.wait_for_timeout(50)
    check(await px(RED) > 10, 'wodospad: pomyłka zaznaczona na dole toru')
    await page.evaluate('__in.fire([0x80,37,0])')

    await opt(page, '#viewSeg >> text=Bez nut')
    check(not await page.is_visible('#view') and not await page.evaluate("document.body.classList.contains('withView')"), 'bez nut: widok schowany')

    # tryb „W tempie”: pięciolinia przesuwa się płynnie z czasem
    await opt(page, '#viewSeg >> text=Nuty')
    await opt(page, '#modeSeg >> text=W tempie')
    await page.click('#playBtn')
    await page.wait_for_timeout(900)
    p = await page.evaluate('vw.pos')
    check(0 < p < 3 and p != int(p), 'w tempie pięciolinia przesuwa się płynnie (pozycja %.2f)' % p)
    await page.click('#playBtn')
    await opt(page, '#modeSeg >> text=Czekaj na mnie')
    await page.click('#playBtn')


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
        await route_piano(page)
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

        await view_tests(page, check)
        await options_menu_tests(page, check)

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

        # Brzmienie fortepianu: pobrane raz przy pierwszym dźwięku, zapisane w IndexedDB, po przeładowaniu z pamięci
        await page.wait_for_function("piano.state === 'ready' || piano.state === 'error'", timeout=10000)
        check(await page.evaluate("piano.state") == 'ready', 'fortepian wczytany ' + str(await page.evaluate("piano.msg")))
        check(await page.evaluate("Object.keys(piano.bufs).length") == 88, 'fortepian ma 88 nut')
        check(await page.evaluate("Object.values(piano.bufs).every(b => b.numberOfChannels === 1 && b.duration <= PIANO_SEC + 0.01)"),
              'próbki mono i przycięte')
        check(HITS['piano'] == 1, 'próbki pobrane raz (zapytań: %d)' % HITS['piano'])
        check(await page.evaluate("idbGet(PIANO_KEY).then(t => !!t && t.length > 1000)"), 'próbki zapisane w IndexedDB')
        made = await page.evaluate("""() => { let made = 0; const o = actx.createBufferSource;
            actx.createBufferSource = function () { made++; return o.call(this); };
            tone(60, 0.3); tone(110, 0.3); tone(10, 0.3); return made; }""")
        check(made == 3, 'tone() gra próbkami, też poza zakresem 21–108 (%d)' % made)
        if not await page.evaluate("document.querySelector('#settings').classList.contains('open')"):
            await page.click('#openSettings')
        check('gotowy' in await page.text_content('#pianoStatus'), 'Ustawienia pokazują stan fortepianu')
        await page.click('#voiceTestBtn')
        await page.select_option('#voiceSel', 'synth')
        check(await page.evaluate("S.voice") == 'synth' and 'prosty' in (await page.text_content('#pianoStatus')).lower(),
              'można wybrać prosty dźwięk')
        made = await page.evaluate("""() => { let made = 0; const o = actx.createOscillator;
            actx.createOscillator = function () { made++; return o.call(this); }; tone(60, 0.3); return made; }""")
        check(made == 1, 'prosty dźwięk gra syntezatorem')
        await page.select_option('#voiceSel', 'piano')
        await page.reload()
        await page.wait_for_timeout(300)
        await page.evaluate("ensureAudio()")
        await page.wait_for_function("piano.state === 'ready'", timeout=10000)
        check(await page.evaluate("piano.fromCache") and HITS['piano'] == 1,
              'po przeładowaniu fortepian z pamięci, bez pobierania (zapytań: %d)' % HITS['piano'])

        check(not errors, 'brak błędów JS ' + (str(errors) if errors else ''))
        await browser.close()

    print('\nWYNIK:', 'wszystko OK' if not failures else f'{len(failures)} błąd(y)')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    asyncio.run(main())

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


def tempo_track(bpm):
    us = round(60e6 / bpm)
    ev = bytes([0x00, 0xFF, 0x51, 0x03]) + us.to_bytes(3, 'big') + bytes([0x00, 0xFF, 0x2F, 0x00])
    return b'MTrk' + struct.pack('>I', len(ev)) + ev


# Techno: 130 BPM, perkusja (kanał 10), bas syntezatorowy i melodia na „Lead 2 (sawtooth)”
DANCE_MIDI = song_midi(
    tempo_track(130),
    track('Drums', 0, 9, [36, 38] * 30, 48),
    track('Bass', 38, 1, [36, 36, 43, 41] * 12, 48),
    track('Lead', 81, 0, [72, 74, 76, 79, 76, 74, 72, 71] * 6, 48),
)
# Zespół: perkusja, gitary, bas, bez syntezatorów (100 BPM)
BAND_MIDI = song_midi(
    tempo_track(100),
    track('Drums', 0, 9, [36, 38] * 30, 96),
    track('Bass', 33, 1, [36, 43, 41, 38] * 12, 96),
    track('Guitar', 27, 2, [[60, 64, 67], [57, 60, 64]] * 12, 192),
    track('Melody', 65, 3, [72, 74, 76, 79, 76, 74, 72, 71] * 6, 96),
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


async def go_home(page):
    """Wraca do biblioteki (osobny ekran), jeśli jesteśmy na ekranie grania."""
    if await page.is_visible('#backBtn'):
        await page.click('#backBtn')


async def open_catalog(page):
    await go_home(page)
    await page.click('#openCatalog')


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
# paleta „Noc”: RIGHT / LEFT – prawa (pomarańczowa) / lewa (niebieska) ręka, NOW_R – aktualny pasek prawej ręki w wodospadzie,
# MISS – pomyłka (różowo-czerwona)
RIGHT, LEFT, NOW_R, MISS = [255, 159, 28], [79, 163, 255], [255, 190, 92], [255, 92, 122]


async def tap_outside(page):
    """Stuknięcie obok menu „Opcje” (w tytuł utworu w nagłówku) – zamyka menu."""
    box = await page.locator('#songTitle').bounding_box()
    await page.mouse.click(box['x'] + 10, box['y'] + box['height'] / 2)


async def opt(page, selector):
    """Kliknięcie w menu „Opcje” (tryb, tempo, transpozycja, dźwięk, widok) – otwiera je, gdy jest zamknięte."""
    if await page.evaluate("document.querySelector('#opts').hidden"):
        await page.click('#optsBtn')
    await page.click(selector)


async def hands_tests(page, check):
    """Podział nut na ręce (kolory w wodospadzie): nazwy ścieżek, średnia wysokość, jedna ścieżka na obie ręce."""
    r = await page.evaluate("""() => {
      const run = (tracks, notes) => { const s = {tracks}, f = hands(s, notes); return notes.map(n => f(n)).join(''); };
      const gama = BUILTIN.find(b => b.title.startsWith('Gama')), list = gama.notes.map(n => ({m: n.note, track: n.track}));
      const f = hands(gama, list);
      return {
        gama: list.every(n => f(n) === (n.track === 1 ? 'L' : 'R')),
        twoUnnamed: run(['Track 1', 'Track 2'], [{m: 72, track: 0}, {m: 76, track: 0}, {m: 45, track: 1}, {m: 48, track: 1}]),
        bothHigh: run(['Melody', 'Chords'], [{m: 76, track: 0}, {m: 79, track: 0}, {m: 62, track: 1}, {m: 64, track: 1}]),
        onePiano: run(['Piano'], [{m: 48, track: 0}, {m: 52, track: 0}, {m: 72, track: 0}, {m: 76, track: 0}]),
        melody: run(['Lead'], [{m: 67, track: 0}, {m: 71, track: 0}, {m: 59, track: 0}, {m: 72, track: 0}, {m: 74, track: 0}, {m: 76, track: 0}, {m: 77, track: 0}]),
      }; }""")
    check(r['gama'], 'ręce: „Prawa ręka” / „Lewa ręka” z nazw ścieżek')
    check(r['twoUnnamed'] == 'RRLL', 'ręce: dwie ścieżki bez nazw – niższa to lewa ' + r['twoUnnamed'])
    check(r['bothHigh'] == 'RRLL', 'ręce: obie ścieżki wysoko – niższa (akordy) to lewa ' + r['bothHigh'])
    check(r['onePiano'] == 'LLRR', 'ręce: jedna ścieżka na obie ręce – podział na C4 ' + r['onePiano'])
    check(r['melody'] == 'RRRRRRR', 'ręce: sama melodia – cała prawą ręką ' + r['melody'])


async def options_menu_tests(page, check):
    """Pasek odtwarzacza: na wierzchu tylko Start/cofnij/dalej/od początku/suwak, reszta w menu „Opcje”."""
    check(not await page.is_visible('#modeSeg') and not await page.is_visible('#speed') and not await page.is_visible('#viewSeg'),
          'tryb, tempo i widok schowane w menu „Opcje”')
    for sel in ('#playBtn', '#restartBtn', '#prevBtn', '#nextBtn', '#pos', '#optsBtn'):
        check(await page.is_visible(sel), 'na wierzchu: ' + sel)
    lay = await page.evaluate("""() => { const t = document.querySelector('#transport').getBoundingClientRect(),
        k = document.querySelector('#kbd').getBoundingClientRect(), r = document.querySelector('#right').getBoundingClientRect();
        return {above: t.bottom <= k.top, inside: t.left >= r.left - 1 && t.right <= r.right + 1}; }""")
    check(lay['above'] and lay['inside'], 'pływający odtwarzacz leży nad klawiaturą, w prawej kolumnie ' + str(lay))
    check(await page.get_attribute('#playBtn', 'aria-label') in ('Start', 'Pauza') and await page.query_selector('#playBtn svg'),
          'Start/Pauza: ikona i opis dla czytnika')
    await page.click('#optsBtn')
    pop = await page.evaluate("""() => { const p = document.querySelector('#opts').getBoundingClientRect(),
        b = document.querySelector('#optsBtn').getBoundingClientRect(); return p.bottom <= b.top && p.top >= 0; }""")
    check(pop, 'menu „Opcje” otwiera się w górę i mieści na ekranie')
    check(await page.is_visible('#modeSeg') and await page.is_visible('#speed') and await page.is_visible('#trUp')
          and await page.is_visible('#sound') and await page.is_visible('#viewSeg'), 'menu „Opcje” pokazuje wszystkie opcje')
    sum0 = await page.text_content('#optsSum')
    await page.click('#trUp')
    check('+1' in await page.text_content('#optsSum'), 'podsumowanie na przycisku pokazuje transpozycję (%s)' % await page.text_content('#optsSum'))
    await page.click('#trDown')
    check(await page.text_content('#optsSum') == sum0, 'transpozycja wraca do 0')
    await tap_outside(page)  # stuknięcie obok menu
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
    check(await px(RIGHT) > 30, 'pięciolinia: aktualna nuta w kolorze prawej ręki (pomarańczowa)')
    check(await px(MISS) > 30, 'pięciolinia: pomyłka (trzymany klawisz) różowo-czerwona')
    await page.evaluate('__in.fire([0x80,61,0])')
    await page.wait_for_timeout(100)
    check(await px(MISS) == 0, 'po puszczeniu klawisza nuta pomyłki znika')
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
    check(await px(NOW_R) > 30, 'wodospad: nuta do zagrania przy klawiaturze (jaśniejsza, z poświatą)')
    check(await px(RIGHT) > 30 and await px(LEFT) == 0, 'wodospad: melodia (prawa ręka) pomarańczowa, bez lewej ręki')
    lay = await page.evaluate("""() => { const t = document.querySelector('#transport'), v = document.querySelector('#view').getBoundingClientRect(),
        k = document.querySelector('#kbd').getBoundingClientRect();
        return {inView: t.parentNode.id === 'view', top: t.getBoundingClientRect().top - v.top, full: v.width >= innerWidth - 1,
                tall: v.height / (k.top - document.querySelector('header').getBoundingClientRect().bottom)}; }""")
    check(lay['inView'] and lay['top'] < 30 and lay['full'] and lay['tall'] > 0.65,
          'wodospad: odtwarzacz u góry wodospadu, wodospad zajmuje większość ekranu ' + str(lay))
    check(await page.evaluate("document.querySelectorAll('#felt i').length") >= 1, 'filc świeci nad zapalonym klawiszem')
    n0 = (await page.evaluate('steps[stepIdx].notes'))[0]
    check(await page.evaluate(f"""(() => {{ const g = kGeom.get({n0}), cv = document.querySelector('#viewCv');
        const x = Math.round((g.l + g.w / 2) * cv.width), d = cv.getContext('2d').getImageData(x, cv.height - 12, 1, 1).data;
        return d[0] > 240 && d[1] > 165 && d[1] < 215 && d[2] < 140; }})()"""), 'wodospad: pasek stoi nad właściwym klawiszem')
    await page.evaluate('__in.fire([0x90,37,90])')
    await page.wait_for_timeout(50)
    check(await px(MISS) > 10, 'wodospad: pomyłka zaznaczona na dole toru')
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


async def demo_tests(page, check):
    """Tryb „Pokaz”: aplikacja sama gra utwór na keyboardzie (Note On / Note Off), klawisze na ekranie się wciskają,
    nuty spływają w wodospadzie, trafień nie liczymy; pauza wycisza keyboard."""
    view0 = await page.evaluate('S.view')
    await opt(page, '#modeSeg >> text=Pokaz')
    check(await page.evaluate("S.mode") == 'demo' and await page.evaluate("S.view") == 'fall', 'pokaz: włącza się wodospad')
    check('Pokaz' in await page.text_content('#optsSum') and await page.text_content('#stats') == '', 'pokaz: opis na przycisku, bez statystyk')
    await tap_outside(page)
    await page.evaluate('__sent.length = 0')
    await page.click('#playBtn')
    await page.wait_for_timeout(700)
    sent = await page.evaluate('__sent')
    pc = [i for i, m in enumerate(sent) if m == [0xC0, 0]]
    ons = [m for m in sent if m[0] == 0x90]
    check(pc and [0xB0, 0, 0] in sent[:pc[0]] and pc[0] < sent.index(ons[0]) if ons else False,
          'pokaz: przed nutami przełącza keyboard na fortepian (Bank Select + Program Change C0 00)')
    first = await page.evaluate('ns[0].m')
    check(len(ons) >= 2 and ons[0][1] == first and ons[0][2] > 0, 'pokaz: wysyła nuty do keyboardu (Note On %s)' % ons[:3])
    check(any(m[0] == 0x80 for m in sent), 'pokaz: puszcza nuty (Note Off)')
    check(any(m[0] == 0xA2 and m[2] > 0 for m in sent), 'pokaz: diody na keyboardzie świecą')
    press = await page.evaluate("[...document.querySelectorAll('.key.press')].map(e => +e.dataset.n)")
    sounding = await page.evaluate('[...demoOn.keys()]')
    check(len(press) >= 1 and set(press) <= set(sounding) | set(await page.evaluate('[...lit]')), 'pokaz: grane klawisze na ekranie wciśnięte ' + str(press))
    check(await page.evaluate("getComputedStyle(document.querySelector('.key.press')).transform") != 'none', 'pokaz: wciśnięty klawisz jest niżej')
    check(await page.evaluate(COUNT_PX, NOW_R) > 30, 'pokaz: aktualna nuta świeci w wodospadzie')
    good0 = await page.evaluate('good + bad')
    await page.evaluate('__in.fire([0x90,61,90]); __in.fire([0x80,61,0])')
    check(await page.evaluate('good + bad') == good0, 'pokaz: klawisze z keyboardu nie liczą się jako pomyłki')
    await page.evaluate('__sent.length = 0')
    await page.click('#playBtn')  # pauza
    sent = await page.evaluate('__sent')
    check(await page.evaluate('demoOn.size') == 0 and [0xB0, 123, 0] in sent and not await page.query_selector('.key.press'),
          'pokaz: pauza wycisza keyboard (Note Off + All Notes Off)')
    # bez keyboardu gra iPad
    r = await page.evaluate("""() => { const o = out, calls = []; const t0 = window.tone; out = null; window.tone = (...a) => calls.push(a);
        demoNote(ns[0]); window.tone = t0; out = o; return {sent: demoOn.size}; }""")
    check(r['sent'] == 0, 'pokaz: bez keyboardu nic nie wysyła')
    # brzmienie Pokazu: brzmienie utworu, „nie zmieniaj” (brzmienie z keyboardu), Pokaz na iPadzie (keyboard tylko świeci)
    r = await page.evaluate("""() => { const res = {}; const run = (k, d, v) => { S.kbdMode = k; S.demoOut = d;
          if (v) S.songVoice[song.id] = v; else delete S.songVoice[song.id];
          __sent.length = 0; kbdVoice(true); demoNote(ns[0]);
          const x = {pc: __sent.filter(m => m[0] === 0xC0).map(m => m[1]), on: __sent.filter(m => m[0] === 0x90).length}; demoSilence(); return x; };
        res.ep = run('song', 'kbd', 'epiano'); res.kbd = run('kbd', 'kbd'); res.ipad = run('song', 'ipad');
        S.kbdMode = 'song'; S.demoOut = 'kbd'; delete S.songVoice[song.id]; return res; }""")
    check(r['ep'] == {'pc': [4], 'on': 1}, 'pokaz: gra brzmieniem utworu (pianino elektryczne → C0 04) ' + str(r['ep']))
    check(r['kbd'] == {'pc': [], 'on': 1}, 'pokaz: „nie zmieniaj” nie zmienia programu keyboardu ' + str(r['kbd']))
    check(r['ipad'] == {'pc': [], 'on': 0}, 'pokaz na iPadzie nie wysyła nut ani programu do keyboardu ' + str(r['ipad']))
    await opt(page, '#modeSeg >> text=Czekaj na mnie')
    await opt(page, '#viewSeg >> text=' + {'off': 'Bez nut', 'staff': 'Nuty', 'fall': 'Wodospad'}[view0])
    await tap_outside(page)
    await page.click('#playBtn')


async def voice_tests(page, check):
    """Brzmienie dobrane do utworu: propozycja aplikacji, zmiana dla utworu w menu Opcje, Program Change dla keyboardu,
    synteza na iPadzie."""
    # propozycje dla różnych utworów
    sug = await page.evaluate("""() => { const v = s => suggestVoice(s).v, B = t => BUILTIN.find(b => b.title.startsWith(t));
        const fake = (title, src) => ({title, src, notes: [], tracks: [], inst: []});
        return {kotek: v(B('Wlazł kotek')), oda: v(B('Oda do radości')), gama: v(B('Gama')),
          darude: v(fake('Darude – Sandstorm', 'lakh:x')), bach: v(fake('Bach – Invention 1', 'commons:1')),
          toccata: v(fake('Bach – Toccata and Fugue in D minor', 'bitmidi:1')), jingle: v(fake('Jingle Bells', 'bitmidi:2')),
          bb2017: v(fake('Ed Sheeran – Shape of You', 'billboard:2017/1/2017_01_full.mid')),
          bb1972: v(fake('Roberta Flack – The First Time', 'billboard:1972/1/1972_01_full.mid')),
          bb1958: v(fake('Domenico Modugno – Volare', 'billboard:1958/1/1958_01_full.mid')),
          chopin: v(fake('Chopin – Nocturne Op. 9 No. 2', 'lakh:x'))}; }""")
    want = {'kotek': 'box', 'oda': 'piano', 'gama': 'piano', 'darude': 'synth', 'bach': 'harpsi', 'toccata': 'organ', 'jingle': 'box',
            'bb2017': 'pop', 'bb1972': 'epiano', 'bb1958': 'piano', 'chopin': 'piano'}
    check(sug == want, 'propozycje brzmienia z tytułu, wykonawcy i roku przeboju ' + str({k: v for k, v in sug.items() if want[k] != v}))
    r = await page.evaluate("""([d, b, p]) => { const P = (x, t) => parseMidi(new Uint8Array(x).buffer, t);
        const dance = P(d, 'Nieznany 1'), band = P(b, 'Nieznany 2'), pop = P(p, 'Nieznany 3');
        return {dance: suggestVoice(dance), band: suggestVoice(band).v, pop: suggestVoice(pop).v, drums: dance.drums, bpm: dance.bpm}; }""",
        [list(DANCE_MIDI), list(BAND_MIDI), list(POP_MIDI)])
    check(r['drums'] == 60 and r['bpm'] == 130, 'parser liczy perkusję i tempo (%s, %s BPM)' % (r['drums'], r['bpm']))
    check(r['dance']['v'] == 'synth' and 'perkusja' in r['dance']['why'], 'techno z pliku (syntezator + perkusja, 130 BPM) → syntezator dance ' + str(r['dance']))
    check(r['band'] == 'epiano' and r['pop'] == 'pop', 'zespół → pianino elektryczne, wolna piosenka z syntezatorami → syntezator pop ' + str(r))

    # utwór z syntezatorem: przy otwarciu keyboard przełącza się na „Lead 1 (square)” (C0 50)
    await page.evaluate('__sent.length = 0')
    await add_song(page, POP_MIDI, 'Piosenka z syntezatorem')
    await page.wait_for_function("song && song.title === 'Piosenka z syntezatorem'")
    sent = await page.evaluate('__sent')
    check([0xC0, 80] in sent and [0xB0, 0, 0] in sent, 'otwarcie utworu przełącza keyboard na jego brzmienie (C0 50)')
    check('Syntezator pop' in await page.text_content('#optsSum'), 'na przycisku Opcje nazwa brzmienia (%s)' % await page.text_content('#optsSum'))
    await page.click('#optsBtn')
    ui = await page.evaluate("""() => ({n: document.querySelectorAll('#voiceSeg button').length,
        on: [...document.querySelectorAll('#voiceSeg button.on')].map(b => b.dataset.voice),
        star: [...document.querySelectorAll('#voiceSeg button')].filter(b => b.querySelector('.star')).map(b => b.dataset.voice),
        why: document.querySelector('#voiceWhy').textContent})""")
    check(ui['n'] == 7 and ui['on'] == ['pop'] and ui['star'] == ['pop'] and 'syntezatory' in ui['why'],
          'menu Opcje: 7 brzmień, wybrana i z gwiazdką propozycja ' + str(ui))
    # zmiana brzmienia dla utworu
    await page.evaluate('__sent.length = 0')
    await page.click('#voiceSeg button[data-voice="organ"]')
    await page.wait_for_timeout(200)
    sent = await page.evaluate('__sent')
    sv = await page.evaluate("JSON.parse(localStorage.getItem('sk_settings')).songVoice[song.id]")
    check(sv == 'organ' and await page.evaluate("voiceOf(song)") == 'organ', 'wybór brzmienia zapamiętany dla utworu (%s)' % sv)
    check([0xC0, 19] in sent and any(m[0] == 0x90 for m in sent), 'zmiana brzmienia: keyboard przełączony (C0 13) i zagrana próbka')
    ui = await page.evaluate("""() => ({on: [...document.querySelectorAll('#voiceSeg button.on')].map(b => b.dataset.voice),
        why: document.querySelector('#voiceWhy').textContent})""")
    check(ui['on'] == ['organ'] and 'Wybrane przez Ciebie' in ui['why'], 'menu pokazuje wybór ręczny ' + str(ui))
    # synteza na iPadzie: organy to kilka oscylatorów, nie próbki fortepianu
    made = await page.evaluate("""() => { ensureAudio(); let osc = 0, buf = 0; const o = actx.createOscillator, b = actx.createBufferSource;
        actx.createOscillator = function () { osc++; return o.call(this); }; actx.createBufferSource = function () { buf++; return b.call(this); };
        tone(60, 0.3); const res = {osc, buf}; VOICE_IDS.filter(v => v !== 'piano').forEach(v => tone(62, 0.3, 0, 0.2, null, v));
        res.all = osc; actx.createOscillator = o; actx.createBufferSource = b; return res; }""")
    check(made['osc'] == 5 and made['buf'] == 0 and made['all'] > 15, 'iPad gra organy syntezą (oscylatory: %s, próbki: %s)' % (made['osc'], made['buf']))
    # gwiazdka wraca do propozycji
    await page.click('#voiceSeg button[data-voice="pop"]')
    check(await page.evaluate("!S.songVoice[song.id] && voiceOf(song) === 'pop'"), 'stuknięcie w propozycję wraca do automatu')
    # „Zawsze fortepian” w Ustawieniach
    await page.evaluate("S.voice = 'piano'; renderVoices()")
    check(await page.evaluate("voiceOf(song)") == 'piano' and not await page.query_selector('#voiceSeg .star'), 'zawsze fortepian: bez propozycji')
    await page.evaluate("S.voice = 'auto'; renderVoices()")
    # „nie zmieniaj brzmienia keyboardu”
    r = await page.evaluate("""() => { S.kbdMode = 'kbd'; __sent.length = 0; kbdVoice(true); const n = __sent.filter(m => m[0] === 0xC0).length;
        S.kbdMode = 'song'; return n; }""")
    check(r == 0, '„nie zmieniaj” – brak Program Change')
    await tap_outside(page)
    # powrót do biblioteki – keyboard wraca do fortepianu
    await page.evaluate('__sent.length = 0')
    await go_home(page)
    check([0xC0, 0] in await page.evaluate('__sent'), 'po powrocie do biblioteki keyboard wraca do fortepianu (C0 00)')
    # usunięcie utworu czyści jego wybór
    await page.evaluate("""() => { const u = userSongs[userSongs.length - 1]; S.songVoice[u.id] = 'box'; removeUserSong(u); }""")
    check(await page.evaluate("Object.keys(S.songVoice).length") == 0, 'usunięcie utworu czyści jego brzmienie')


async def library_tests(page, check):
    """Biblioteka (osobny ekran): karty, najnowsze na górze, wbudowane na końcu, Edytuj/Usuń, szukanie, filtr poziomu, katalog."""
    for k, t in enumerate(LIB_TITLES):
        src = ('lakh:x/%d' % k) if k < 9 else ('bitmidi:%d' % k) if k < 11 else None
        await add_song(page, TINY_MIDI, t, src, select=False)
    await page.evaluate("userSongs.forEach((u, i) => u.lvl = [1, 2, 3][i % 3]); saveUser(); renderLib()")
    await go_home(page)
    rows = await page.eval_on_selector_all('#lib .song.user', 'els => els.map(e => e.querySelector(".tt").textContent)')
    check(len(rows) == 12 and rows[0] == 'Satie – Gymnopédie No. 1',
          'Twoje utwory: wszystkie, najnowsze na górze ' + str(rows[:2]))
    order = await page.eval_on_selector_all('#lib .song', 'els => els.map(e => e.classList.contains("builtin"))')
    check(order == [False] * 12 + [True] * 6, 'wbudowane na końcu listy')
    box = await page.evaluate("""() => { const sc = document.querySelector('#home').getBoundingClientRect();
        const r = [...document.querySelectorAll('#lib .song')].filter(e => { const b = e.getBoundingClientRect(); return b.top >= sc.top && b.bottom <= sc.bottom; });
        return {h: sc.height, visible: r.length}; }""")
    check(box['visible'] >= 8, 'w poziomie (1180×820) widać co najmniej 8 kart ' + str(box))
    abba = await page.evaluate("""() => { const r = [...document.querySelectorAll('#lib .song')].find(e => e.querySelector('.tt').textContent === 'Dancing Queen');
        return r ? r.querySelector('.sub').textContent : null; }""")
    check(abba is not None and 'ABBA' in abba and 'Lakh' in abba and 'Łatwe' in abba, 'Lakh: tytuł, pod nim wykonawca, poziom i źródło ' + str(abba))
    check(await page.evaluate("document.querySelectorAll('#lib .song .bars i.on').length") > 12, 'poziom pokazany kreskami')
    own = await page.evaluate("document.querySelector('#lib .song .sub').textContent")
    check('własny plik' in own, 'plik bez źródła opisany jako „własny plik” ' + own)
    check(await page.eval_on_selector_all('#lib .del', 'e => e.length') == 0, 'bez „Edytuj” nie ma przycisków usuwania')
    check(await page.evaluate("userSongs.every(u => Array.isArray(u.roll))"), 'pobrane utwory mają zapisaną miniaturę melodii')

    # wyszukiwanie (od razu, także we wbudowanych) i filtr poziomu
    await page.fill('#libQ', 'abba')
    check(await page.eval_on_selector_all('#lib .song', 'e => e.length') == 1, 'szukanie „abba” zostawia 1 utwór')
    await page.fill('#libQ', 'gymnopedie')
    check(await page.eval_on_selector_all('#lib .song', 'e => e.length') == 1, 'szukanie bez polskich/obcych znaków')
    await page.fill('#libQ', 'kotek')
    check(await page.eval_on_selector_all('#lib .song.builtin', 'e => e.length') == 1, 'szukanie obejmuje wbudowane')
    await page.fill('#libQ', 'xyzxyz')
    check('Żaden utwór nie pasuje' in await page.text_content('#lib'), 'komunikat, gdy nic nie pasuje')
    check('xyzxyz' in await page.text_content('#libFind'), 'przycisk „Szukaj … w katalogu”')
    await page.fill('#libQ', '')
    check(await page.text_content('#libFind') == '', 'bez zapytania nie ma przycisku katalogu')
    await page.click('#libLvlSeg >> text=Trudne')
    lv = await page.eval_on_selector_all('#lib .song .lvl', 'els => els.map(e => e.textContent)')
    check(len(lv) == 4 and set(lv) == {'Trudne'}, 'filtr poziomu „Trudne” ' + str(lv))
    await page.click('#libLvlSeg >> text=Wszystkie')

    # Edytuj → Usuń (tylko pobrane)
    await page.click('#libEdit')
    check(await page.eval_on_selector_all('#lib .del', 'e => e.length') == 12 and await page.text_content('#libEdit') == 'Gotowe',
          '„Edytuj” pokazuje „Usuń” przy każdym pobranym utworze')
    await page.click('#lib .song >> nth=1')
    check(await page.evaluate("document.body.classList.contains('home')") and await page.evaluate("!song || song.title !== 'Für Elise full version'"),
          'w trybie edycji stuknięcie nie otwiera utworu')
    for _ in range(3):
        await page.click('#lib .song >> nth=0 >> .del')
    check(await page.evaluate("userSongs.length") == 9, 'usuwanie działa')
    await page.click('#libEdit')
    check(await page.eval_on_selector_all('#lib .del', 'e => e.length') == 0, '„Gotowe” chowa przyciski usuwania')
    await page.evaluate("userSongs.length = 0; saveUser(); renderLib()")
    check(await page.eval_on_selector_all('#lib .song.builtin', 'e => e.length') == 6 and 'katalog' in (await page.text_content('#lib')).lower()
          and not await page.is_visible('#libEdit'), 'pusta lista: wbudowane, podpowiedź o katalogu, bez „Edytuj”')


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

        check('połączony' in await page.text_content('#status') and 'Bluetooth Session 1' in await page.get_attribute('#status', 'title'), 'wykrywa keyboard')
        check(await page.evaluate("document.body.classList.contains('home')") and not await page.is_visible('#kbd'),
              'start: ekran biblioteki (bez klawiatury)')
        lib = await page.eval_on_selector_all('#lib .song.builtin', 'els => els.map(e => e.querySelector(".tt").textContent + "|" + e.querySelector(".lvl").textContent)')
        check('Wlazł kotek na płotek|Łatwe' in lib and 'Dla Elizy – początek|Średnie' in lib, 'wbudowane utwory mają poziom ' + str(lib))
        check(await page.eval_on_selector_all('#lib .song.builtin .roll rect', 'e => e.length') > 30, 'karty mają miniaturę melodii')
        check(not await page.is_visible('#resume'), 'bez historii nie ma kafelka „Graj dalej”')

        # Tryb „Czekaj na mnie”: Oda do radości zaczyna się od E4 (MIDI 64 -> światło 43)
        await page.click('text=Oda do radości – Beethoven')
        check(not await page.evaluate("document.body.classList.contains('home')") and await page.is_visible('#kbd')
              and await page.is_visible('#backBtn') and not await page.is_visible('#home'), 'stuknięcie w kartę otwiera ekran grania')
        await page.click('#playBtn')
        await page.wait_for_timeout(100)
        sent = await page.evaluate('__sent')
        check([0xA2, 43, 1] in sent, 'zapala pierwszy klawisz (A2 2b 01)')
        await page.evaluate('__in.fire([0x90,64,90]); __in.fire([0x80,64,0])')
        await page.wait_for_timeout(150)
        check('krok 2' in await page.text_content('#posTxt'), 'po trafieniu przechodzi do kroku 2')
        await page.evaluate('__in.fire([0x90,61,90])')
        check('Pomyłki 1' in await page.text_content('#stats'), 'liczy pomyłkę')

        await hands_tests(page, check)
        await view_tests(page, check)
        await demo_tests(page, check)
        await options_menu_tests(page, check)

        # Powrót do biblioteki: zapamiętane miejsce i „Graj dalej”
        step = await page.evaluate('stepIdx')
        await page.click('#backBtn')
        check(await page.evaluate("document.body.classList.contains('home')") and await page.evaluate('!playing'), '„Biblioteka” wraca do listy i zatrzymuje granie')
        check(await page.is_visible('#resume') and 'Oda do radości' in await page.text_content('#resume'), 'kafelek „Graj dalej” z ostatnim utworem')
        await page.click('#resumeBtn')
        check(await page.evaluate('song.title') == 'Oda do radości – Beethoven' and await page.evaluate('stepIdx') == step,
              '„Graj dalej” wraca do tego samego kroku (%s)' % step)
        await go_home(page)

        # Cały utwór na dwie ręce (akordy)
        await page.click('text=Gama C-dur (obie ręce)')
        await page.click('#playBtn')
        keys = await page.evaluate("""() => ({lh: [...document.querySelectorAll('.key.lit.lh')].map(e => +e.dataset.n),
            rh: [...document.querySelectorAll('.key.lit:not(.lh)')].map(e => +e.dataset.n), felt: document.querySelectorAll('#felt i.lh').length})""")
        check(keys['lh'] == [48] and keys['rh'] == [60] and keys['felt'] == 1, 'klawisze świecą w kolorach rąk (C3 lewa, C4 prawa) ' + str(keys))
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
        star = await page.eval_on_selector_all('#tracks .chip', 'els => els.map(e => !!e.querySelector(".star"))')
        check(len(chips) == 3 and len(on) == 1 and on[0].startswith('Synth') and star.count(True) == 1 and star[chips.index([on[0], True])],
              'piosenka: zaznaczona tylko melodia (z gwiazdką) ' + str(chips))
        check('Lead 2 (sawtooth)' in on[0] and any('Electric Bass (finger)' in c[0] for c in chips), 'ścieżki pokazują instrument')
        check(await page.evaluate('ns.every(n => n.m >= 71)'), 'odtwarzacz dostaje tylko nuty melodii')
        await page.click('#tracks .chip >> text=Bass')
        check(await page.evaluate('sel.size') == 2, 'można dołączyć bas')
        await add_song(page, PIANO_MIDI, 'Fortepian')
        await page.wait_for_function("song && song.title === 'Fortepian'")
        check(await page.evaluate('sel.size') == 2 and await page.evaluate('song.melody') == -1, 'fortepian na dwie ręce: obie ścieżki')
        await voice_tests(page, check)
        await page.evaluate("userSongs.length = 0; saveUser(); renderLib()")

        await library_tests(page, check)

        # Katalog utworów (odpowiedzi bibliotek są podstawione, bez internetu)
        await mock_catalog(page)
        # jedna wyszukiwarka: Enter w bibliotece, gdy nic nie pasuje, szuka w katalogu
        await go_home(page)
        await page.fill('#libQ', 'chopin testowy')  # Lakh tego nie zna, więc wyniki są tylko z podstawionych bibliotek
        await page.press('#libQ', 'Enter')
        await page.wait_for_selector('.cat', timeout=3000)
        check(await page.evaluate("document.querySelector('#catalog').classList.contains('open') && document.querySelector('#catQ').value === 'chopin testowy'"),
              'Enter w wyszukiwarce biblioteki (nic nie pasuje) szuka w katalogu')
        await page.evaluate("document.querySelector('#libQ').value = ''; renderLib()")
        sugg = await page.eval_on_selector_all('#catSugg .sgroup', 'els => els.map(e => e.textContent)')
        check(len(sugg) >= 3 and any('Better Off Alone' in g for g in sugg) and any('ABBA' in g for g in sugg), 'podpowiedzi pop i dance ' + str(sugg))
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
        await open_catalog(page)
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

        # Hity (Billboard): spis z bimmuda.json (prawdziwy plik), pliki z raw.githubusercontent.com (podstawione)
        await open_catalog(page)
        sugg = await page.eval_on_selector_all('#catSugg .sgroup', 'els => els.map(e => e.textContent)')
        check(any('Nowe hity' in g and 'Ed Sheeran' in g and 'Justin Bieber' in g for g in sugg), 'podpowiedzi „Nowe hity” ' + str(sugg))
        await page.click('#catSrcSeg >> text=Billboard')
        await page.fill('#catQ', 'ed sheeran')
        await page.press('#catQ', 'Enter')
        await page.wait_for_selector('.cat .badge.billboard', timeout=5000)
        titles = await page.eval_on_selector_all('.cat .t b', 'els => els.map(e => e.textContent)')
        check(titles == ['Ed Sheeran – Shivers', 'Ed Sheeran – Perfect', 'Ed Sheeran – Shape of You', 'Ed Sheeran – Thinking Out Loud'],
              'Billboard: hity Eda Sheerana, najnowsze najpierw ' + str(titles))
        url = await page.evaluate("cat.items[0].url")
        check(url.startswith('https://raw.githubusercontent.com/madelinehamilton/BiMMuDa/') and url.endswith('/bimmuda_dataset/2022/5/2022_05_full.mid'),
              'adres pliku Billboard ' + url)
        meta = await page.text_content('.cat >> nth=0 >> small')
        check('hit 2022' in meta and 'sama melodia' in meta, 'Billboard: rok hitu i „sama melodia” ' + meta)
        await page.click('#catSrcSeg >> text=Wszystkie')
        await page.click('#catSugg >> text=Justin Bieber')
        await page.wait_for_selector('.cat .badge.billboard', timeout=5000)
        titles = await page.eval_on_selector_all('.cat .t b', 'els => els.map(e => e.textContent)')
        check(titles[0] == 'Justin Bieber – Love Yourself' and 'Kid Laroi and Justin Bieber – Stay' in titles,
              '„Wszystkie”: hity Biebera z Billboardu na górze ' + str(titles[:5]))
        await page.wait_for_function("catA.active === 0 && !catA.queue.length", timeout=5000)
        await page.click('.cat >> nth=0 >> text=Pobierz')
        await page.wait_for_selector('.cat >> nth=0 >> text=Mam', timeout=3000)
        check(await page.evaluate("userSongs.some(u => u.src === 'billboard:2016/1/2016_01_full.mid')"), 'hit z Billboardu trafia do „Moje utwory”')
        await page.click('#closeCatalog')
        row = await page.evaluate("[...document.querySelectorAll('#lib .song')].map(e => e.textContent).find(t => t.includes('Love Yourself'))")
        check(row is not None and row.startswith('Love Yourself') and 'Justin Bieber' in row and 'Billboard' in row,
              'Billboard: tytuł w 1. linii, wykonawca·źródło w 2. ' + str(row))

        await page.evaluate("userSongs.length = 0; saveUser(); renderLib()")
        await open_catalog(page)
        await page.click('#catSrcSeg >> text=Wszystkie')
        await page.click('#closeCatalog')

        await mock_catalog(page, bitmidi_ok=False)
        await open_catalog(page)
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
        await page.select_option('#voiceSel', 'piano')
        check(await page.evaluate("S.voice") == 'piano', 'Ustawienia: można wybrać „zawsze fortepian”')
        await page.select_option('#voiceSel', 'auto')
        await page.select_option('#demoOutSel', 'ipad')
        check(await page.evaluate("S.demoOut") == 'ipad', 'Ustawienia: Pokaz na iPadzie')
        await page.select_option('#demoOutSel', 'kbd')
        # ustawienia sprzed tej zmiany (Pokaz „fortepian z iPada”, prosty dźwięk) przechodzą na nowe
        await page.evaluate("""localStorage.setItem('sk_settings', JSON.stringify(Object.assign(JSON.parse(localStorage.getItem('sk_settings')),
            {voice: 'synth', demoVoice: 'ipad', voiceVer: undefined, songVoice: undefined, kbdMode: undefined, demoOut: undefined})))""")
        await page.reload()
        await page.wait_for_timeout(300)
        await page.evaluate("ensureAudio()")
        await page.wait_for_function("piano.state === 'ready'", timeout=10000)
        check(await page.evaluate("piano.fromCache") and HITS['piano'] == 1,
              'po przeładowaniu fortepian z pamięci, bez pobierania (zapytań: %d)' % HITS['piano'])
        mig = await page.evaluate("({v: S.voice, d: S.demoOut, k: S.kbdMode, sv: S.songVoice, old: 'demoVoice' in S, ver: S.voiceVer})")
        check(mig == {'v': 'auto', 'd': 'ipad', 'k': 'song', 'sv': {}, 'old': False, 'ver': 2}, 'stare ustawienia brzmienia przeniesione ' + str(mig))

        check(not errors, 'brak błędów JS ' + (str(errors) if errors else ''))
        await browser.close()

    print('\nWYNIK:', 'wszystko OK' if not failures else f'{len(failures)} błąd(y)')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    asyncio.run(main())

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
URL = 'file://' + os.path.join(ROOT, 'index.html')

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
HITS = {'commons': 0, 'bitmidi': 0}
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
        await page.goto(URL)
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

        # Katalog utworów (odpowiedzi bibliotek są podstawione, bez internetu)
        await mock_catalog(page)
        await page.click('#openCatalog')
        await page.fill('#catQ', 'chopin')
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


asyncio.run(main())

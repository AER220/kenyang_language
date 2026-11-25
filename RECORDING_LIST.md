# Recording list: numbers

What to record next, and what the sources say for each. **Listen, don't read:** where the
sources differ, the forms are shown side by side so you can say the number as you say it,
not as one of them writes it. Write the form you said in the "You say" column.

By the variants order in CLAUDE.md, a recording outranks everything. As soon as one is in
`audio_words.json`, Nɛpɛ́m teaches it, with no other change. To add one:

1. Save the file in `audio/` under the name in the last column.
2. Add `{"file": "<that name>", "kenyang": "<what you said>", "english": "<the English>"}`
   to `audio_words.json`. The English must be the number in words ("eleven",
   "twenty-one"), so the code can tell it is a number.
3. Run `python build_audio_manifest.py`.

Not Kenyang to learn from: this file lists what the sources say, including forms nobody
has confirmed. It must never go in `knowledge_base/`.

## 1. Eleven to twenty: confirmed in your verified text, not yet recorded

| # | English | What the sources give | | You say | Save as |
|---|---|---|---|---|---|
| 11 | eleven | Byó nɛ amɔt *(verified, course, book)*<br>byó nɛ amot *(course)*<br>byó ne amɔt *(book)* | **differ: listen** | | `109_eleven.mp3` |
| 12 | twelve | Byó nɛ bɛ́pay *(verified, course, book)*<br>byó nɛ bépay *(course)*<br>byó ne bepay *(book)* | **differ: listen** | | `110_twelve.mp3` |
| 13 | thirteen | Byó nɛ bɛ́rát *(verified, course, book)*<br>byó nɛ bérát *(course)*<br>byó ne bérát *(book)* | **differ: listen** | | `111_thirteen.mp3` |
| 14 | fourteen | Byó nɛ mɛ́nwi *(verified, course, book)*<br>byó nɛ ánwi *(verified)*<br>byó nɛ ménwi *(course)*<br>byó ne ménwi *(book)* | **differ: listen** | | `112_fourteen.mp3` |
| 15 | fifteen | Nɛkú *(verified, course, book)* | agree | | `113_fifteen.mp3` |
| 16 | sixteen | Nɛkú nɛ amɔ́t *(verified, book)*<br>nekú ne émot *(course)*<br>nɛkú nɛ amɔt *(course)* | **differ: listen** | | `114_sixteen.mp3` |
| 17 | seventeen | Nɛkú nɛ bɛ́pay *(verified, course, book)*<br>nɛkú nɛ bépay *(course)* | **differ: listen** | | `115_seventeen.mp3` |
| 18 | eighteen | Nɛkú nɛ bɛ́rat *(verified, book)*<br>nɛkú nɛ bɛ́rát *(course, book)*<br>nɛkú ne bérát *(course)* | **differ: listen** | | `116_eighteen.mp3` |
| 19 | nineteen | Nɛkú nɛ mɛ́nwi *(verified, course, book)*<br>nɛkú nɛ ménwi *(course)* | **differ: listen** | | `117_nineteen.mp3` |
| 20 | twenty | Ɛsa *(verified, course, book)*<br>Esa *(course, book)*<br>ɛ̌kwɔ́t *(book)* | **differ: listen** | | `118_twenty.mp3` |

## 2. The pattern numbers

One of each way the system joins. With these, the counting rule may be able to fill the
rest; without them it cannot (see `docs/numbers/numbers_1_to_100.md`). The MISSING ones
are blank: fill them by saying them.

| # | English | What the sources give | | You say | Save as |
|---|---|---|---|---|---|
| 21 | twenty-one | ɛsa nsɛm émot *(course)*<br>ɛsa nsɛm meso ɛ́mɔt *(course)*<br>Ɛsa nsɛm ɛ́mɔt *(book)*<br>esa nsem émɔt *(book)*<br>ɛsa nsɛm ɛ́mot *(book)* | **differ: listen** | | `119_twenty-one.mp3` |
| 22 | twenty-two | ɛsa nsɛm meso ɛ́pay *(course)*<br>Ɛsa nsɛm bɛ́pay *(book)* | **differ: listen** | | `120_twenty-two.mp3` |
| 25 | twenty-five | ɛsa nsɛm meso ɛ́tay *(course)* | one source only | | `121_twenty-five.mp3` |
| 27 | twenty-seven | ɛsa nsɛm meso tándrámɔt *(course)* | one source only | | `122_twenty-seven.mp3` |
| 31 | thirty-one | Ɛsa nsɛm byó nɛ amɔ́t *(book)* | one source only | | `123_thirty-one.mp3` |
| 35 | thirty-five | — | **MISSING**: no source has it | | `124_thirty-five.mp3` |
| 36 | thirty-six | — | **MISSING**: no source has it | | `125_thirty-six.mp3` |
| 41 | forty-one | Bɛsa bɛ́pay nɛ ɛ́mɔ́t *(book)* | one source only | | `126_forty-one.mp3` |
| 55 | fifty-five | — | **MISSING**: no source has it | | `127_fifty-five.mp3` |
| 70 | seventy | bɛsa bɛ́rát nsɛm byó *(course, book)*<br>bhesa bhérát nsɛm byó *(course)*<br>bɛsa bɛ́pay nsɛm byó *(book)*<br>Bɛsa bɛ́rat nsɛm byó *(book)*<br>besa bépay nsem byó *(book)*<br>besa bérát nsem byó *(book)* | **differ: listen** | | `128_seventy.mp3` |
| 90 | ninety | bɛsa mɛ́nwi nsɛm byó *(course, book)*<br>bhɛsa ménwi nsɛm byó *(course)*<br>besa ménwi nsem byó *(book)* | **differ: listen** | | `129_ninety.mp3` |
| 99 | ninety-nine | — | **MISSING**: no source has it | | `130_ninety-nine.mp3` |

Fourteen has two forms in your own verified text (`Byó nɛ mɛ́nwi` in the speaker file,
`byó nɛ ánwi` in the recorded texts). Your recording of it settles which Nɛpɛ́m teaches.

## 3. The body words: 41 not yet recorded

The English is what the picture matches your recording on. **Type it exactly as in the
second column**: the same words, nothing added or dropped ("back of the head", not "back
of head"; "tooth", not "teeth"). Capitals and punctuation do not matter. When your
recording's English matches exactly one of these, the picture teaches your word and
keeps the form below as "also written"; the publish log lists every one.

**Before you record on your phone, read this.** The pictures count only *your own*
recordings, the ones in `audio_words.json`. A recording sent from the website goes to
the Review page with every other speaker's, and the pictures do not count those, on
purpose (one approved typo must not vouch for itself). So recorded on the phone today,
these would play in the chat and on the site but would **not** move up on the pictures.
See QUESTIONS 29 for the two ways to fix that.

| # | English, exactly | What the picture shows now | Now | You say |
|---|---|---|---|---|
| 1 | `hair` | Emeneh *(head and mouth)* | from written sources | |
| 2 | `forehead` | Nefó *(head and mouth)* | from written sources | |
| 3 | `eye` | amík *(head and mouth)* | verified, not recorded | |
| 4 | `nose` | N'nyuen *(head and mouth)* | from written sources | |
| 5 | `nostril` | Mboko n'nyuen *(head and mouth)* | from written sources | |
| 6 | `cheek` | Atah *(head and mouth)* | from written sources | |
| 7 | `lip` | Ebhebhe Nnyu *(head and mouth)* | from written sources | |
| 8 | `chin` | Enyiak *(head and mouth)* | from written sources | |
| 9 | `jaw` | Eghebe Nnyu *(head and mouth)* | from written sources | |
| 10 | `neck` | Emirh *(head and mouth)* | from written sources | |
| 11 | `throat` | Ngongho *(head and mouth)* | from written sources | |
| 12 | `mouth` | N'Nyu *(head and mouth)* | from written sources | |
| 13 | `tongue` | Nereurh *(head and mouth)* | from written sources | |
| 14 | `tooth` | Nenyen *(head and mouth)* | from written sources | |
| 15 | `head` | ntí *(body)* | verified, not recorded | |
| 16 | `back of the head` | Nnere Nti *(body)* | from written sources | |
| 17 | `shoulder` | Nenkirh *(body)* | from written sources | |
| 18 | `armpit` | Ewap *(body)* | from written sources | |
| 19 | `chest` | Ebhokewad *(body)* | from written sources | |
| 20 | `ribs` | Mbiapak *(body)* | from written sources | |
| 21 | `stomach` | Menay *(body)* | from written sources | |
| 22 | `navel` | Netong *(body)* | from written sources | |
| 23 | `lower abdomen` | Ntenne mmieng *(body)* | from written sources | |
| 24 | `back` | Nsem *(body)* | from written sources | |
| 25 | `waist` | Ebhóh *(body)* | from written sources | |
| 26 | `buttocks` | Bheraka nned *(body)* | from written sources | |
| 27 | `arm` | Ereb awuor *(body)* | from written sources | |
| 28 | `elbow` | Nnere amoh *(body)* | from written sources | |
| 29 | `palm` | Nekak awuor *(body)* | from written sources | |
| 30 | `finger` | sɛnɔŋ-áwɔ́ *(body)* | verified, not recorded | |
| 31 | `fingernail` | Ne'nyaï *(body)* | from written sources | |
| 32 | `knee` | Nehnen *(body)* | from written sources | |
| 33 | `calf` | Sechoko *(body)* | from written sources | |
| 34 | `foot` | Neyard ekak *(body)* | from written sources | |
| 35 | `heel` | Nned ekak *(body)* | from written sources | |
| 36 | `toe` | Senong Ekak *(body)* | from written sources | |
| 37 | `toenail` | Amaï bhekak *(body)* | from written sources | |
| 38 | `skin` | Nkwor mmuet *(body)* | from written sources | |
| 39 | `breast` | Nebheurh *(body)* | from written sources | |
| 40 | `vagina` | Nekwed *(body)* | from written sources | |
| 41 | `anus` | Mboko nned *(body)* | from written sources | |

# Backlog

This file lists the remaining issues/features need addressing. Whenever an issues is confirmed done/fixed, update the item from [ ] to [X]. Never delete this file.

- [ ] Create TTC and OFC versions of the fonts

- [X] Prepare 2 packages to submit to Google Fonts: one with Heiti fonts (regular+bold variants) and one with Songti fonts (regular+bold variants), and save them to @release folder


- [X] In the Heiti variants, the pinyin overlaps with next character pinyins. Make sure pinyin width do not exceed 98% hanzi width. You can compress pinyins horizontally to fit. But keep vertical heights consistent.

- [ ] Removes the references to refdata in filenames and text files

- [X] Read all data from reference font data/FangZhengKaiTiPinYinZiKu-1.ttc so that in the following building process, it is no longer needed.

- [X] Create a md file with sample text in Chinese (~20 chinese characters with 6 to 1 readings, in descending order) to show off these fonts capabilities; plus test text in English, then translated to Vietnamese,Russian, Greek, Malay. Each text is render to pdf in Sans then in Serif variant 1 to 6

- [X] The pinyin on top is too close the characters. Need to add a space. Refer to the reference font. Remember to update config.json for this parameter.

- [X] Creates bold variants of the NanGuo Sans Pinyin font with the basefont of NotoSansSC-Bold.ttf

- [X] Creates serif regular variants of the NanGuo Serif Pinyin font with the basefont of NotoSerifSC-Regular.ttf

- [X] Cut the gap between ruby and hazi to about 2/3 of current value

- [X] Creates serif bold variants of the NanGuo Serif Pinyin font with the basefont of NotoSerifSC-Bold

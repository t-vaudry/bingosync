Third-Party Notices
===

#### HPBingoCounter

The counter role's goal counting is ported from
[HPBingoCounter](https://github.com/nt5664/HPBingoCounter) by
[nt5664](https://github.com/nt5664), a desktop app for counters following
Harry Potter bingo boards. Ported pieces:

- the per-goal fields a counter needs (`id`, `amount`, `uniqueAmount`,
  `triggers`), in `bingosync-app/bingosync/generators/bingo_generator.py`
- the counting rules: per-goal counts, linked goals moving with the goal that
  triggers them, and save / load / clear / reset of the counts, in
  `CounterTally` (`bingosync-app/bingosync/models/rooms.py`) and
  `bingosync-app/static/bingosync/room/counter.js`

HPBingoCounter is licensed under the MIT License:

```
MIT License

Copyright (c) 2024 nt5664

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

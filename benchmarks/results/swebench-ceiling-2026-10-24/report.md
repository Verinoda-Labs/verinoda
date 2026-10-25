run / arm | lanes | graded | resolved | not counted | flagged first/last | sensitivity | $/session | turns | s/session | recall (resolved) | verbatim | resolved w/o verbatim on fn>=2
C0 (D184's harness, repeat 1) / plain | 34 | 33 | 6 | 1 | 1/0 | 6 of 32 | 0.088 | 7.3 | 44 | 0.59 | 3 | 3
C0 (D184's harness, repeat 1) / guided | 34 | 31 | 7 | 3 | 1/0 | 7 of 31 | 0.146 | 9.0 | 247 | 0.71 | 2 | 5
C1 Sonnet / plain | 100 | 99 | 73 | 0 | 6/0 | 68 of 93 | 0.089 | 7.7 | 198 | 0.48 | 23 | 64
C1 Sonnet / guided | 100 | 99 | 73 | 0 | 5/0 | 69 of 94 | 0.116 | 9.8 | 248 | 0.53 | 29 | 61
C4 Opus / plain | 100 | 99 | 84 | 0 | 5/0 | 80 of 94 | 0.202 | 9.3 | 135 | 0.74 | 49 | 65
C4 Opus / guided | 100 | 99 | 85 | 0 | 4/0 | 81 of 95 | 0.276 | 13.2 | 162 | 0.76 | 47 | 66
C4 Fable / plain | 100 | 99 | 87 | 0 | 5/0 | 82 of 94 | 0.856 | 14.6 | 207 | 0.80 | 54 | 63
C4 Fable / guided | 38 | 37 | 34 | 0 | 0/0 | 34 of 37 | 1.032 | 19.5 | 250 | 0.71 | 19 | 25
C3 attempt 2 (Opus) / plain | 100 | 99 | 84 | 0 | 4/0 | 80 of 95 | 0.195 | 9.4 | 104 | 0.75 | 50 | 64
C3 attempt 2 (Opus) / guided | 100 | 99 | 88 | 0 | 1/0 | 87 of 98 | 0.266 | 12.5 | 173 | 0.78 | 54 | 64
C3 attempt 3 (Opus) / plain | 100 | 99 | 83 | 0 | 0/0 | 83 of 99 | 0.194 | 9.2 | 92 | 0.74 | 49 | 63
C3 attempt 3 (Opus) / guided | 100 | 99 | 87 | 0 | 2/0 | 86 of 97 | 0.259 | 12.6 | 167 | 0.76 | 52 | 65
diagnostic: hints / plain | 3 | 3 | 0 | 0 | 0/0 | 0 of 3 | 0.388 | 17.3 | 228 | 0.00 | 0 | 0
diagnostic: hints / guided | 3 | 3 | 1 | 0 | 0/0 | 1 of 3 | 0.440 | 20.0 | 233 | 0.60 | 0 | 1
diagnostic: tests / plain | 3 | 3 | 3 | 0 | 0/0 | 3 of 3 | 0.267 | 10.7 | 100 | 0.71 | 2 | 2
diagnostic: tests / guided | 3 | 3 | 3 | 0 | 0/0 | 3 of 3 | 0.281 | 13.7 | 138 | 0.41 | 1 | 3

C0 (D184's harness, repeat 1), guided - plain: n 31: 5 vs 7 (discordant 2/4), difference +0.065 [-0.097, +0.226], McNemar p 0.688
C1 Sonnet, guided - plain: n 99: 73 vs 73 (discordant 3/3), difference +0.000 [-0.051, +0.051], McNemar p 1.000
C4 Opus, guided - plain: n 99: 84 vs 85 (discordant 3/4), difference +0.010 [-0.040, +0.061], McNemar p 1.000
C4 Fable, guided - plain: n 37: 35 vs 34 (discordant 1/0), difference -0.027 [-0.081, +0.000], McNemar p 1.000
C3 attempt 2 (Opus), guided - plain: n 99: 84 vs 88 (discordant 1/5), difference +0.040 [+0.000, +0.091], McNemar p 0.219
C3 attempt 3 (Opus), guided - plain: n 99: 83 vs 87 (discordant 0/4), difference +0.040 [+0.010, +0.081], McNemar p 0.125
diagnostic: hints, guided - plain: n 3: 0 vs 1 (discordant 0/1), difference +0.333 [+0.000, +1.000], McNemar p 1.000
diagnostic: tests, guided - plain: n 3: 3 vs 3 (discordant 0/0), difference +0.000 [+0.000, +0.000], McNemar p 1.000
C4 Opus - C1 Sonnet, plain: n 99: 73 vs 84 (discordant 0/11), difference +0.111 [+0.051, +0.172], McNemar p 0.001
C4 Opus - C1 Sonnet, guided: n 99: 73 vs 85 (discordant 2/14), difference +0.121 [+0.051, +0.202], McNemar p 0.004
C4 Fable - C1 Sonnet, plain: n 99: 73 vs 87 (discordant 1/15), difference +0.141 [+0.071, +0.222], McNemar p 0.001
C4 Fable - C1 Sonnet, guided: n 37: 29 vs 34 (discordant 1/6), difference +0.135 [+0.000, +0.270], McNemar p 0.125
C4 Fable - C4 Opus, plain: n 99: 84 vs 87 (discordant 3/6), difference +0.030 [-0.030, +0.091], McNemar p 0.508
C4 Fable - C4 Opus, guided: n 37: 35 vs 34 (discordant 2/1), difference -0.027 [-0.135, +0.054], McNemar p 1.000
C4's rule (amendment 9: reported, chooses nothing): plain arms, Opus 84 of 100, Fable 87 of 100; over Fable's 138 lanes: Opus 119, Fable 121; over the 136 of them graded for both: Opus 119, Fable 121

closed-book probe, 99 instances answered by every model run so far (claude-sonnet-5-5, claude-opus-5-5, claude-fable-5-1):
  claude-sonnet-5-5  1-4 lines  n  58: closed-book mean 0.58, verbatim 29 | with the repository (c1-s1, plain) mean 0.47, verbatim 21 (n 58)
  claude-sonnet-5-5  5-9 lines  n  22: closed-book mean 0.44, verbatim  6 | with the repository (c1-s1, plain) mean 0.36, verbatim  3 (n 22)
  claude-sonnet-5-5  10- lines  n  19: closed-book mean 0.45, verbatim  3 | with the repository (c1-s1, plain) mean 0.18, verbatim  0 (n 19)
  claude-sonnet-5-5  all        n  99: closed-book mean 0.52, verbatim 38 | with the repository (c1-s1, plain) mean 0.39, verbatim 24 (n 99)
  claude-opus-5-5    1-4 lines  n  58: closed-book mean 0.72, verbatim 34 | with the repository (c4-opus, plain) mean 0.67, verbatim 34 (n 58)
  claude-opus-5-5    5-9 lines  n  22: closed-book mean 0.61, verbatim  7 | with the repository (c4-opus, plain) mean 0.67, verbatim 11 (n 22)
  claude-opus-5-5    10- lines  n  19: closed-book mean 0.50, verbatim  2 | with the repository (c4-opus, plain) mean 0.56, verbatim  5 (n 19)
  claude-opus-5-5    all        n  99: closed-book mean 0.65, verbatim 43 | with the repository (c4-opus, plain) mean 0.65, verbatim 50 (n 99)
  claude-fable-5-1   1-4 lines  n  58: closed-book mean 0.84, verbatim 43 | with the repository (c4-fable, plain) mean 0.79, verbatim 39 (n 58)
  claude-fable-5-1   5-9 lines  n  22: closed-book mean 0.77, verbatim 14 | with the repository (c4-fable, plain) mean 0.70, verbatim 11 (n 22)
  claude-fable-5-1   10- lines  n  19: closed-book mean 0.76, verbatim 10 | with the repository (c4-fable, plain) mean 0.61, verbatim  6 (n 19)
  claude-fable-5-1   all        n  99: closed-book mean 0.81, verbatim 67 | with the repository (c4-fable, plain) mean 0.73, verbatim 56 (n 99)

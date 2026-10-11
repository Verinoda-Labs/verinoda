# Elle kontrol: ana koşu (40 iddia, kol gizli)

Her iddia için: `grade:` correct / incorrect / not_in_gold (altına göre; altının ne doğruladığı ne yalanladığı bir iddia not_in_gold), `stance:` fact / inference (düz ifade mi, 'likely / appears / may / probably' gibi çekinceli mi). Kol bilgisi `hand_check_key.json`'da; açma.

## 1. `da4ce376d1` — sharkdp__bat-trap-1 (r3)
**Soru:** When a theme defines no gutter foreground color, bat falls back to 256-color palette index 238 for the grid and line numbers; why was that particular shade chosen?
**Altın:** (tuzak) depoda cevap yok — The value 238 was already there in the Initial commit 8f5a80ea (2018-04-21), as `Fixed(238)` in main.rs, and that commit has no body. Every later commit carried the value along without saying why: a979608f 'Add Git support, closes #8', 6b507d1e 'Print filename' and fcfc7c46 'Code cleanup' (all 2018-
**İddia:** The dim default is a known trade-off.

grade: 
stance: 

## 2. `f7a3576576` — fastapi__full-stack-fastapi-template-why-1 (r1)
**Soru:** Why does the reset_password endpoint read the new password from the request body and not from a query parameter?
**Altın:** The new password was moved from a query parameter to a body parameter for security; the commit points to a discussion of why query-string parameters are unsafe even over HTTPS.; The endpoint still takes the password in a body model (NewPassword) today.
**İddia:** Commit b4fa418 appears to be the change that moved the reset token into the body.

grade: 
stance: 

## 3. `400a8e7482` — guzzle__guzzle-trap-1 (r2)
**Soru:** Why does the message formatter's debug log template mark the request and the response with rows of '>' and '<' characters and the error with a row of dashes?
**Altın:** (tuzak) depoda cevap yok — git blame and git log -L on the DEBUG constant line go back through three commits. 77844559 (2019-12-21, #2462) only added the public visibility keyword to constants. 861d2da5 (2015-06-13) fixed the common log format, added date_* patterns and closes #1122; it did not change DEBUG. b58db450 (2015-04
**İddia:** The request follows a row of '>', the response follows a row of '<', and the error follows a row of dashes.

grade: 
stance: 

## 4. `5f6c4485ac` — gin-gonic__gin-trap-1 (r3)
**Soru:** Why does aborting a request set the context's handler index to half of the largest int8 value rather than to the maximum int8 value itself?
**Altın:** (tuzak) depoda cevap yok — The value math.MaxInt8 / 2 arrived in the initial commit 15216a0 (2014-06-18, message 'Initial commit', no body). After that: aa9fad5 (2015-03-25, 'Fixes NoMethod / NoRoute handlers', no body) removed the AbortIndex constant; 31323f6 (2015-03-26, 'AbortIndex is missing', no body) put it back as cons
**İddia:** safeInt8 caps the handler count at math.MaxInt8, and index is an int8.

grade: 
stance: 

## 5. `cb50fa79e1` — google__gson-trap-1 (r3)
**Soru:** Why is the streaming JSON reader's internal character buffer sized at exactly 1024 characters rather than some other size?
**Altın:** (tuzak) depoda cevap yok — BUFFER_SIZE = 1024 (JsonReader.java:258) came from 6e06bf0d (2021-11-09, 'Fix for an ArrayIndexOutOfBoundsException'). Its body only says fillBuffer changes pos, so caching pos is wrong; it moved the existing literal 1024 into a constant and gives no reason for the size. The commits that git log -S"
**İddia:** Commit 6e06bf0d ("Fix for an ArrayIndexOutOfBoundsException") later touched the BUFFER_SIZE constant.

grade: 
stance: 

## 6. `ee64ab9f1d` — fastapi__full-stack-fastapi-template-trap-1 (r2)
**Soru:** Why do access tokens default to expiring after eight days?
**Altın:** (tuzak) depoda cevap yok — The value 60 * 24 * 8 came in with the initial import. git log -S finds only 7f8bfc8 (2019-02-09, 'First commit, from couchbase generator, basic changes'), whose body says only 'not tested / updated yet'. git log -L over the lines then lists these commits: a21978e ('Update config for PostgreSQL', no
**İddia:** The value is probably a long-lived convenience default chosen so users stay logged in for about a week.

grade: 
stance: 

## 7. `8dd42465fd` — sharkdp__bat-why-1 (r3)
**Soru:** When the 'changes' style component is enabled, why does the printer add the git change-marker sidebar only if the file actually has modified lines, and not every time the component is turned on?
**Altın:** Before this change, `--style=changes` always printed a 2-space indent, even for a file with no modifications.; The change makes the indent appear only when the sidebar has at least one +/- git marker (PR #3406).
**İddia:** line_changes is None for non-file inputs or when git cannot produce a diff; stdin gets no line-changes data.

grade: 
stance: 

## 8. `b0d82006eb` — junegunn__fzf-why-1 (r2)
**Soru:** In the Unix terminal renderer's cancellable key-read path, why does an interrupted select() call loop forever instead of counting toward a retry limit?
**Altın:** Counting EINTR against the 100-iteration limit (meant for read attempts, reset only when a byte was read) let signals during an idle prompt drain it; running out returned getCharError, which became a Fatal event and exit status 2.; Only the cancellable path (used with --listen) is affected, because select() is not restarted by SA_RESTART, unlike the blocking read on the non-cancellable path.; The fix matches waitReadable(), which already retries EINTR without a limit; it fixes issue #4917.
**İddia:** The loop exits when the cancel pipe becomes readable, returning getCharCancelled.

grade: 
stance: 

## 9. `c99703f2c8` — Graphify-Labs__graphify-why-1 (r3)
**Soru:** On Windows, why does _rebuild_lock take its msvcrt lock on a byte far into the lock file instead of the first byte?
**Altın:** Windows byte-range locks are mandatory, so locking at offset 4096 lets external readers still read the owning PID written at byte 0 without getting a PermissionError.; The commit added msvcrt locking because the Windows fallback of yielding True left concurrent rebuilds unserialized, and they collided on .graph.tmp.json (closes #3881).
**İddia:** The code seeks to the offset before every msvcrt.locking call: blocking acquire, non-blocking acquire and release with LK_UNLCK, each locking 1 byte.

grade: 
stance: 

## 10. `718192604e` — fastapi__sqlmodel-why-1 (r1)
**Soru:** Why does the library's core model and SQL expression code import Literal from the standard typing module instead of from typing_extensions?
**Altın:** Literal is imported from typing directly because support for Python 3.8 had been dropped, so the typing_extensions backport was no longer needed.
**İddia:** The change to import Literal from typing was enabled by dropping Python 3.8 support, so the typing_extensions backport was no longer needed.

grade: 
stance: 

## 11. `4d7a348bb1` — fastapi__full-stack-fastapi-template-why-1 (r1)
**Soru:** Why does the reset_password endpoint read the new password from the request body and not from a query parameter?
**Altın:** The new password was moved from a query parameter to a body parameter for security; the commit points to a discussion of why query-string parameters are unsafe even over HTTPS.; The endpoint still takes the password in a body model (NewPassword) today.
**İddia:** git log -S for the body code only turns up 8558cf0, a file move (#630), which shows when the code moved, not why.

grade: 
stance: 

## 12. `1c7edb23b3` — sharkdp__bat-trap-1 (r2)
**Soru:** When a theme defines no gutter foreground color, bat falls back to 256-color palette index 238 for the grid and line numbers; why was that particular shade chosen?
**Altın:** (tuzak) depoda cevap yok — The value 238 was already there in the Initial commit 8f5a80ea (2018-04-21), as `Fixed(238)` in main.rs, and that commit has no body. Every later commit carried the value along without saying why: a979608f 'Add Git support, closes #8', 6b507d1e 'Print filename' and fcfc7c46 'Code cleanup' (all 2018-
**İddia:** The repository does not state why 238 was chosen; no comment, commit message, or doc gives a reason.

grade: 
stance: 

## 13. `e9785c2dd1` — sharkdp__bat-affects-1 (r1)
**Soru:** If the signature or return type of get_pager_executable were changed, which code would have to be updated?
**Altın:** The function is defined in src/config.rs, and the unit tests in the same file call it directly.; The paged --help path in the bat binary calls it to pick the pager for the help output.; The bugreport (--diagnostic) path calls it and falls back to "less" when it returns None.
**İddia:** invoke_bugreport at src/bin/bat/main.rs:289-292 calls get_pager_executable and falls back to "less" via unwrap_or_else when it returns None, assuming an Option<String> return.

grade: 
stance: 

## 14. `25a8019d1b` — axios__axios-when-1 (r3)
**Soru:** When did axios's map of HTTP status codes get the UnprocessableContent name for 422, and which change added it?
**Altın:** UnprocessableContent: 422 was added on 2026-08-04 in 'feat(HttpStatusCode): add RFC 9110 aliases for 413 and 422 (#11082)'. The same change added ContentTooLarge for 413.
**İddia:** HEAD is 84a9f3b 'prepare release 1.20.0' and 39955a6 is an ancestor of HEAD.

grade: 
stance: 

## 15. `1425c004cb` — Graphify-Labs__graphify-trap-1 (r1)
**Soru:** Why was 20,000 characters chosen as the per-file limit for text sent to the LLM during semantic extraction, rather than a larger or smaller number?
**Altın:** (tuzak) depoda cevap yok — No commit gives a reason for the number. 5904081 (2026-04-29, 'Add Kimi K2.6 backend, fix phantom god nodes (#598), fix concept file_type (#601)') first added content[:20000] in _read_files; its body is only a Co-Authored-By line. cc5c545 (2026-04-30, 'feat(llm): pack chunks by token budget...') mov
**İddia:** The comment at the constant says _read_files truncates each file at this many characters before joining into the user message, and that token estimates use the same cap so packing matches reality.

grade: 
stance: 

## 16. `30855a14c0` — axios__axios-when-1 (r2)
**Soru:** When did axios's map of HTTP status codes get the UnprocessableContent name for 422, and which change added it?
**Altın:** UnprocessableContent: 422 was added on 2026-08-04 in 'feat(HttpStatusCode): add RFC 9110 aliases for 413 and 422 (#11082)'. The same change added ContentTooLarge for 413.
**İddia:** The checkout's HEAD is 84a9f3b, "chore(release): prepare release 1.20.0".

grade: 
stance: 

## 17. `dac633fead` — junegunn__fzf-affects-1 (r1)
**Soru:** If Chars.ToRunes were changed so that in rune mode it returned a fresh copy instead of the item's own rune slice, or if its signature changed, which code calls it and would need review or updating?
**Altın:** The algo package calls text.ToRunes() in two places, in the exact/equal matching code.; terminal.go calls ToRunes at four sites, among them replace-query, which already copies the result defensively (append([]rune{}, ...)) because the slice is aliased.; Within util, Chars.Lines copies ToRunes() output, and chars_test.go asserts that rune-mode ToRunes aliases the underlying array (&runes[0] == &chars.ToRunes()[0]).
**İddia:** src/util/chars_test.go:259 (TestRuneSlicesAliasTheText) asserts &runes[0] == &chars.ToRunes()[0], would fail if ToRunes returned a copy, and so must change.

grade: 
stance: 

## 18. `54a3e01567` — fastapi__sqlmodel-when-1 (r1)
**Soru:** When did Field's foreign-key on-delete option start accepting RESTRICT as a value, and which change added it?
**Altın:** RESTRICT was added as an allowed on-delete value by commit 86ab09f (2024-07-20), the commit that added cascade delete relationship support: cascade_delete, ondelete and passive_deletes (#983).
**İddia:** The same commit introduced the ondelete option and RESTRICT together, so RESTRICT was accepted from the start.

grade: 
stance: 

## 19. `ae5f0ace6f` — fastapi__sqlmodel-affects-1 (r3)
**Soru:** If I changed the signature or behaviour of is_table_model_class, what code would need to change or could break?
**Altın:** is_table_model_class is defined in sqlmodel/_compat.py, where two functions call it: sqlmodel_validate (lines 294, 319, 330) and sqlmodel_init (line 340).; sqlmodel/main.py imports it and calls it in SQLModelMetaclass.__setattr__ (line 565), SQLModelMetaclass.__delattr__ (line 571), SQLModelMetaclass.__init__ (lines 671-672) and SQLModel.__setattr__ (line 891).
**İddia:** Line 294 is in a function that builds the object with cls.__new__(cls) for non-table classes; lines 319 and 330 decide whether to set __dict__ directly or use setattr and whether to copy relationship attributes.

grade: 
stance: 

## 20. `ae490689d6` — expressjs__express-why-1 (r2)
**Soru:** Why does res.clearCookie throw away any maxAge the caller passes and always overwrite expires with a date in the past, rather than respecting the options it was given?
**Altın:** Commit 82fc12a4 ("Ignore `expires` and `maxAge` in `res.clearCookie()` (#5792)", Jon Church, 2024-08-02) introduced the forced past expires and the deletion of maxAge.; Rationale: res.cookie turns maxAge into a relative expires, so a user-supplied maxAge (or expires) would overwrite the expiration that clearCookie needs. The goal is to stop users from accidentally overriding these values when clearing a cookie, without reworking the relative-expires behaviour of maxAge.; In 4.x this was first only deprecated: commit f42b160b (#5672) added a deprecation notice for res.clearCookie accepting options.maxAge/options.expires.
**İddia:** Other options such as path, domain and secure pass through.

grade: 
stance: 

## 21. `5aae58c2bf` — Graphify-Labs__graphify-trap-1 (r2)
**Soru:** Why was 20,000 characters chosen as the per-file limit for text sent to the LLM during semantic extraction, rather than a larger or smaller number?
**Altın:** (tuzak) depoda cevap yok — No commit gives a reason for the number. 5904081 (2026-04-29, 'Add Kimi K2.6 backend, fix phantom god nodes (#598), fix concept file_type (#601)') first added content[:20000] in _read_files; its body is only a Co-Authored-By line. cc5c545 (2026-04-30, 'feat(llm): pack chunks by token budget...') mov
**İddia:** _FILE_CHAR_CAP = 20_000 is defined at graphify/llm.py:30, and its comment says _read_files truncates each file at that many characters before joining them into the user message.

grade: 
stance: 

## 22. `7be63467ce` — axios__axios-when-1 (r2)
**Soru:** When did axios's map of HTTP status codes get the UnprocessableContent name for 422, and which change added it?
**Altın:** UnprocessableContent: 422 was added on 2026-08-04 in 'feat(HttpStatusCode): add RFC 9110 aliases for 413 and 422 (#11082)'. The same change added ContentTooLarge for 413.
**İddia:** git log -S"UnprocessableContent" on lib/helpers/HttpStatusCode.js returns only this commit.

grade: 
stance: 

## 23. `3c3a1de1b5` — expressjs__express-trap-1 (r1)
**Soru:** Why does a new Express app generate weak ETags by default, with the setting value true also meaning weak, instead of strong ETags?
**Altın:** (tuzak) depoda cevap yok — The default line this.set('etag', 'weak') goes back through two commits. c21226aa (Douglas Christopher Wilson, 2014-05-30, 'improve etag control for res.send') changed this.enable('etag') to this.set('etag', 'weak') and added compileETag, where true and 'weak' both select wetag. Its message body is 
**İddia:** wetag is built with { weak: true } and etag with { weak: false }.

grade: 
stance: 

## 24. `c97c8b84ed` — gin-gonic__gin-when-1 (r1)
**Soru:** When did the request logger get a config option that keeps the URL query string out of the logged path, and in which change?
**Altın:** The SkipQueryString field of LoggerConfig was added on 2026-02-27 in "chore(logger): allow skipping query string output (#4547)". That commit changed logger.go, logger_test.go and docs/doc.md.
**İddia:** db30908 appears to be the introducing change of the option.

grade: 
stance: 

## 25. `f132aba39e` — fastapi__sqlmodel-why-1 (r3)
**Soru:** Why does the library's core model and SQL expression code import Literal from the standard typing module instead of from typing_extensions?
**Altın:** Literal is imported from typing directly because support for Python 3.8 had been dropped, so the typing_extensions backport was no longer needed.
**İddia:** The commit touched sqlmodel/main.py, sqlmodel/sql/expression.py and tests/test_pydantic/test_field.py, and removed a typing_extensions line at sqlmodel/sql/expression.py:37.

grade: 
stance: 

## 26. `141dafc411` — guzzle__guzzle-affects-2 (r1)
**Soru:** Which handlers and tests would break if I changed how ProxyEnv::resolveProxySelection combines the proxy request option with the proxy environment variables?
**Altın:** The cURL factory calls ProxyEnv::resolveProxySelection in three places.; The stream handler calls ProxyEnv::resolveProxySelection when it applies the proxy option. Commit 1ab19ef1 added this call, which made the stream handler resolve environment proxies.; The ProxyEnv unit tests call resolveProxySelection directly.
**İddia:** ProxyEnv::resolveProxySelection first calls ProxyOptions::resolve; an option that sets, bypasses or disables the proxy is final, and only a 'none' result falls through to the environment.

grade: 
stance: 

## 27. `bc9413a877` — expressjs__express-affects-1 (r3)
**Soru:** If the signature or behaviour of the internal setCharset helper changed, which code in the repository would have to be updated or would break?
**Altın:** setCharset is defined and exported in lib/utils.js.; Its only runtime caller is res.send in lib/response.js, which imports it and uses it to set the Content-Type with charset utf-8 for string bodies.; The unit tests in test/utils.js exercise it directly (describe 'utils.setCharset(type, charset)').
**İddia:** The tests pin these behaviours: no arguments returns undefined, no charset returns type unchanged, an existing charset=utf-8 is returned unchanged, adding a charset gives text/html; charset=utf-8, and iso-8859-1 is replaced with utf-8.

grade: 
stance: 

## 28. `9b2e8b2894` — fastapi__sqlmodel-when-1 (r3)
**Soru:** When did Field's foreign-key on-delete option start accepting RESTRICT as a value, and which change added it?
**Altın:** RESTRICT was added as an allowed on-delete value by commit 86ab09f (2024-07-20), the commit that added cascade delete relationship support: cascade_delete, ondelete and passive_deletes (#983).
**İddia:** Commit 86ab09f's diff to sqlmodel/main.py adds the OnDeleteType line as new, along with two ondelete: Union[OnDeleteType, UndefinedType] = Undefined parameters.

grade: 
stance: 

## 29. `733aa2f45b` — expressjs__express-when-1 (r3)
**Soru:** When did res.redirect start emitting deprecation warnings when it is called with a missing or non-string URL or a non-numeric status, and which change added them?
**Altın:** Added by commit c5b8d55a "feat: add deprecation warnings for redirect arguments undefined (#6405)", dated 2025-07-14, by Sebastian Beltran.; The same commit added the depd dependency to lib/response.js and package.json for these warnings.
**İddia:** dbac741a is "5.2.1" in the recent history.

grade: 
stance: 

## 30. `5ef6788c91` — expressjs__express-affects-1 (r1)
**Soru:** If the signature or behaviour of the internal setCharset helper changed, which code in the repository would have to be updated or would break?
**Altın:** setCharset is defined and exported in lib/utils.js.; Its only runtime caller is res.send in lib/response.js, which imports it and uses it to set the Content-Type with charset utf-8 for string bodies.; The unit tests in test/utils.js exercise it directly (describe 'utils.setCharset(type, charset)').
**İddia:** External packages importing express/lib/utils are not visible from this repository.

grade: 
stance: 

## 31. `35959a2b1b` — google__gson-affects-1 (r1)
**Soru:** If I changed the semantics of the reflection helper isAnonymousOrNonStaticLocal (for example, to also treat static local classes as matching), which other production code in Gson would be affected?
**Altın:** Excluder calls ReflectionHelper.isAnonymousOrNonStaticLocal when it decides whether to exclude a class during serialization and deserialization.; ReflectiveTypeAdapterFactory calls it in create(...) for anonymous and local classes, which it does not serialize reflectively.; The helper was introduced in the commit that let anonymous and local classes be serialized with a custom adapter (#2498). That commit touched Excluder, ReflectiveTypeAdapterFactory, ReflectionHelper and the tests for exclusion strategies, enums and objects.
**İddia:** A broader match would exclude static local classes from deserialization, while serialization would not change because of the !serialize guard.

grade: 
stance: 

## 32. `5f23456690` — axios__axios-why-1 (r3)
**Soru:** When toJSONObject converts an object, why does it take each object back out of its set of seen objects once it has finished walking that object's children, instead of leaving it marked as seen for the rest of the conversion?
**Altın:** Removing the object after its children are processed keeps the check limited to the current path (ancestors only). Only a real cycle, meaning an object that contains itself somewhere below it, is skipped.; Without the removal, an object shared by two siblings (a DAG) would be treated as already seen at its second occurrence and dropped as undefined. That is the regression introduced in #7230.; The WeakSet replaced a fixed-size Array(10) with an indexOf lookup. Faster O(1) lookups were a secondary benefit (#10832, fixes #10807).
**İddia:** The object is added to the set at line 970 and removed at line 989, after its children are walked.

grade: 
stance: 

## 33. `7097e414ed` — expressjs__express-trap-1 (r2)
**Soru:** Why does a new Express app generate weak ETags by default, with the setting value true also meaning weak, instead of strong ETags?
**Altın:** (tuzak) depoda cevap yok — The default line this.set('etag', 'weak') goes back through two commits. c21226aa (Douglas Christopher Wilson, 2014-05-30, 'improve etag control for res.send') changed this.enable('etag') to this.set('etag', 'weak') and added compileETag, where true and 'weak' both select wetag. Its message body is 
**İddia:** The message of c21226aa only says 'closes #1435, closes #2129'.

grade: 
stance: 

## 34. `d1a28adf67` — expressjs__express-why-1 (r2)
**Soru:** Why does res.clearCookie throw away any maxAge the caller passes and always overwrite expires with a date in the past, rather than respecting the options it was given?
**Altın:** Commit 82fc12a4 ("Ignore `expires` and `maxAge` in `res.clearCookie()` (#5792)", Jon Church, 2024-08-02) introduced the forced past expires and the deletion of maxAge.; Rationale: res.cookie turns maxAge into a relative expires, so a user-supplied maxAge (or expires) would overwrite the expiration that clearCookie needs. The goal is to stop users from accidentally overriding these values when clearing a cookie, without reworking the relative-expires behaviour of maxAge.; In 4.x this was first only deprecated: commit f42b160b (#5672) added a deprecation notice for res.clearCookie accepting options.maxAge/options.expires.
**İddia:** The commit body says maxAge is ignored to account for the built-in relative expires when passing a maxAge to res.cookie, and that using maxAge to invalidate cookies inherently hit this relative expires behavior.

grade: 
stance: 

## 35. `bb549c1a54` — fastapi__full-stack-fastapi-template-when-1 (r1)
**Soru:** When did the settings start rewriting postgres:// and postgresql:// database URLs to use the psycopg driver, and in which change?
**Altın:** The rewrite was added on 2026-08-11 in commit 32ab6dd ("Migrate to DATABASE_URL instead of separate variables", #2184). That commit replaced the separate POSTGRES_* settings and the computed SQLALCHEMY_DATABASE_URI with a single DATABASE_URL field and its _use_psycopg_driver validator.
**İddia:** The file's most recent changes are d85803b (CORS simplification) and e95e501 (FASTAPI_ENV), both dated 2026-08-10, a day before 32ab6dd, so neither introduced the rewrite.

grade: 
stance: 

## 36. `a34b85f574` — fastapi__sqlmodel-when-1 (r1)
**Soru:** When did Field's foreign-key on-delete option start accepting RESTRICT as a value, and which change added it?
**Altın:** RESTRICT was added as an allowed on-delete value by commit 86ab09f (2024-07-20), the commit that added cascade delete relationship support: cascade_delete, ondelete and passive_deletes (#983).
**İddia:** OnDeleteType is Literal["CASCADE", "SET NULL", "RESTRICT"] at sqlmodel/main.py:93.

grade: 
stance: 

## 37. `aa63555b0e` — guzzle__guzzle-affects-2 (r2)
**Soru:** Which handlers and tests would break if I changed how ProxyEnv::resolveProxySelection combines the proxy request option with the proxy environment variables?
**Altın:** The cURL factory calls ProxyEnv::resolveProxySelection in three places.; The stream handler calls ProxyEnv::resolveProxySelection when it applies the proxy option. Commit 1ab19ef1 added this call, which made the stream handler resolve environment proxies.; The ProxyEnv unit tests call resolveProxySelection directly.
**İddia:** resolveProxySelection first asks ProxyOptions::resolve for a decision from the proxy request option, and returns that result as final if it gave a proxy, bypass or disable.

grade: 
stance: 

## 38. `d1b8f16a9a` — junegunn__fzf-why-1 (r1)
**Soru:** In the Unix terminal renderer's cancellable key-read path, why does an interrupted select() call loop forever instead of counting toward a retry limit?
**Altın:** Counting EINTR against the 100-iteration limit (meant for read attempts, reset only when a byte was read) let signals during an idle prompt drain it; running out returned getCharError, which became a Fatal event and exit status 2.; Only the cancellable path (used with --listen) is affected, because select() is not restarted by SA_RESTART, unlike the blocking read on the non-cancellable path.; The fix matches waitReadable(), which already retries EINTR without a limit; it fixes issue #4917.
**İddia:** SA_RESTART does not restart select(), so the cancellable path sees EINTR, while the non-cancellable blocking read is restarted and does not.

grade: 
stance: 

## 39. `71b20072d1` — google__gson-affects-3 (r1)
**Soru:** If the URL format produced by TroubleshootingGuide.createUrl changed, which parts of Gson that build exception messages would be affected?
**Altın:** createUrl is called from JsonReader (malformed JSON and other syntax errors), TypeToken (raw type tokens and captured type variables), TypeAdapters (java.lang.Class not supported), ReflectiveTypeAdapterFactory (duplicate fields), ConstructorConstructor (R8 abstract class) and ReflectionHelper.; The helper was introduced by 'Link to troubleshooting guide from exception messages (#2357)'.
**İddia:** TypeToken.getTypeTokenTypeArgument uses createUrl("type-token-raw").

grade: 
stance: 

## 40. `728f883a2c` — junegunn__fzf-when-1 (r2)
**Soru:** When did the JSON status that the --listen HTTP server returns for a GET request start including a search progress field, and in which change?
**Altın:** The progress field was added to the Status struct, filled from t.progress in dumpStatus, in commit 901939bd on 2023-09-18 ("Add support for limit and offset parameters for GET / endpoint").
**İddia:** Commit 901939bd (2023-09-18, "Add support for limit and offset parameters for GET / endpoint") added the progress field.

grade: 
stance: 

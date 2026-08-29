# Where this came from, and who else is doing it

I have wanted the law in git for a long time. Not as a product idea: I just
wanted to be able to ask "when did this section change, and what did it say
before", and get an answer the way I would get one about a line of code.

In September 2016 I got as far as [one Act][education-act], the Education Act
1989, converted to a single markdown file and committed to a junk repo. One
commit, 1.5 MB, no versions, no history, no tooling. I never found the time to
do anything more with it, and it sat there for almost exactly ten years until
I picked the idea up again.

So this is not a claim to have invented anything. People have been putting
legislation into git since at least 2009, and several of them got further than
I did, earlier. What follows is what I found when I went looking, partly so
that anyone who lands here can find the thing that actually suits them, and
partly because it would be poor form not to.

## New Zealand

[**nz-statute-book**][nz-statute-book], by John Gregoriadis, is the closest
thing to this, and it got here first: every public Act, every electronic
consolidation, rendered from the PCO's XML and committed with the date the
consolidation took effect. It is a build artefact of [Whiplash][whiplash], a
record of policy reversals in New Zealand. Two things about it I like a lot
and haven't done: it attributes each commit to the government of the day, so
`git shortlog` buckets legislative churn by administration, and it strips the
consolidation furniture so the diffs are only real change. It is one markdown
file per Act rather than per section, which is the main difference between the
two projects. If you want the statute book as documents, look there first.

[**Br3nda/legislation**][br3nda], by Brenda Wallace, is the original as far as
I can tell, and it dates from 2010. It was a nightly spider of the old
legislation website that committed whatever had changed that night, so the
commits are dated to the scrape rather than to the day a version took effect.
It stopped updating not long after it started, but it was doing this fifteen
years ago.

The PCO themselves are worth crediting here, because none of this works
without them. They publish their own XML for every version of every Act, they
have shipped a [v0 API][api] (a key is an email to contact@pco.govt.nz), and
they publish their AI research prototypes as open source under
[nzpco][nzpco], including one on generating prospective consolidations. The
legal position is unusually clear too: there is no copyright in New Zealand
legislation at all, under [section 27 of the Copyright Act 1994][s27].

Different problem, same neighbourhood: [openfisca-aotearoa][openfisca] and the
[Better Rules][better-rules] work from the Service Innovation Lab encode
entitlement rules as executable code, which is Rules as Code rather than text
history. [edithatogo/legislation][edithatogo] is a CLI for searching and
retrieving NZ legislation data.

## Elsewhere

[**BundesGit**][bundesgit] (Stefan Wehrmeyer, 2012, an [Open Knowledge
Labs][okfn-bundesgit] project) put German federal law into git from the
gesetze-im-internet.de XML, and is the best known of these by a distance. It
has been quiet since 2022.

[**Archéo Lex**][archeo-lex] (Sébastien Beyou, 2014) does the same for French
law from the official LEGI database, one markdown file per text. Dormant since
2019.

[**divegeek/uscode**][divegeek] (Shawn Willden, 2009) is the earliest of these
I found, and is now archived. [**nickvido/us-code**][us-code] (2026) is the
current one, built from the OLRC's USLM release points. Their [design
writeup][every-law-a-commit] is the best thing I have read on the file layout
question, and they considered and rejected the per-section layout I use, on
the grounds that ~60,000 files gives you precise diffs but no context and
slower git. That is a fair criticism and I do not think they are wrong about
the trade-off, I just weighted it differently.

[**Legalize**][legalize] (Enrique López, 2026) is the most ambitious of the
lot: the same idea across 31 countries, one repo each, with a
published spec and a conformance checker. There is no New Zealand repo in it,
which seems like a gap someone should fill.

[**droid-f/fedlex**][fedlex] commits Swiss federal data from the Fedlex triple
store as JSON, several times a day. It is metadata rather than rendered law,
but it is the same trick of using git as the change log for an official
dataset, and it is still running.

## The standards and the wider movement

[Akoma Ntoso][akoma-ntoso] (OASIS LegalDocML) is the standard for this
material, and it already has a temporal model derived from FRBR: works,
expressions, manifestations, and machinery for amendments and consolidations.
Monica Palmirani's [Legislative Change Management with Akoma
Ntoso][palmirani] is the reference on the versioning side. There is also a
2025 paper on [component-level versioning of legal norms][component-versioning]
arguing that the existing standards model documents at the macro level and
lack a native mechanism for the granular, provision-level versioning that
point-in-time reconstruction needs, which is a much more rigorous statement of
the thing per-section files are a crude answer to.

[LegalRuleML][legalruleml] is the sibling standard for the rules layer.
[Public.Resource.Org][public-resource] and the free law movement are the
reason a lot of this material is reachable at all, in jurisdictions less
generous than ours. [awesome-legal-data][awesome] is the best index if you
want to keep pulling on this thread.

## What this one does differently

Only really two things, and both are choices rather than advances:

* One file per section, so `git log` and `git blame` work at the granularity
  of a provision rather than an Act. This is the bit the us-code authors
  argued against, and it costs you 379,000 files.
* One sentence per line, so that "omit *fifty*, substitute *one hundred*"
  shows up as a one-line diff rather than a reflowed paragraph.

Neither is novel, and I would not have bothered writing this section if the
rest of the document didn't make it obvious how much prior art there is.

It's public because the legislation is public, and public data should be
available in whatever shape people find useful. That's all.

[akoma-ntoso]: https://www.oasis-open.org/committees/tc_home.php?wg_abbrev=legaldocml
[api]: https://api.legislation.govt.nz/docs/
[archeo-lex]: https://github.com/Legilibre/Archeo-Lex
[awesome]: https://github.com/openlegaldata/awesome-legal-data
[better-rules]: https://serviceinnovationlab.github.io/projects/legislation-as-code/
[br3nda]: https://github.com/Br3nda/legislation
[bundesgit]: https://github.com/bundestag/gesetze
[component-versioning]: https://arxiv.org/html/2506.07853v1
[divegeek]: https://github.com/divegeek/uscode
[edithatogo]: https://github.com/edithatogo/legislation
[education-act]: https://github.com/tonyandrewmeyer/misc/blob/main/education-act-1989.md
[every-law-a-commit]: https://v1d0b0t.github.io/blog/posts/2026-03-29-every-law-a-commit.html
[fedlex]: https://github.com/droid-f/fedlex
[legalize]: https://github.com/legalize-dev/legalize
[legalruleml]: https://www.oasis-open.org/committees/tc_home.php?wg_abbrev=legalruleml
[nz-statute-book]: https://github.com/jonnonz1/nz-statute-book
[nzpco]: https://github.com/nzpco
[okfn-bundesgit]: https://okfnlabs.org/projects/bundesgit/
[openfisca]: https://github.com/BetterRules/openfisca-aotearoa
[palmirani]: https://link.springer.com/chapter/10.1007/978-94-007-1887-6_7
[public-resource]: https://public.resource.org/about/
[s27]: https://www.legislation.govt.nz/act/public/1994/0143/latest/DLM345923.html
[us-code]: https://github.com/nickvido/us-code
[whiplash]: https://github.com/jonnonz1/whiplash

"""Small Act documents, in the shape PCO's XML actually takes."""

# A modern Act: parts, subsections, a repealed section, history notes, and a
# schedule whose two parts each number their clauses from 1.
MODERN = b"""<?xml version="1.0" encoding="UTF-8"?>
<act id="DLM1" year="1961" act.no="43" act.type="public" date.as.at="2020-07-01"
     date.assent="1961-11-01">
 <cover id="DLM2"><title>Example Act 1961</title></cover>
 <front id="DLM3"><long-title id="DLM4"><para><text>An Act to test things.</text></para></long-title></front>
 <body>
  <prov id="DLM5" toc="yes"><label>1</label><heading>Short Title</heading>
   <prov.body><subprov><label>1</label><para><text>This is the Example Act 1961.</text></para></subprov>
    <subprov><label>2</label><para><text>It commences on a day.</text>
     <label-para><label>a</label><para><text>first thing; and</text></para></label-para>
     <label-para><label>b</label><para><text>second thing.</text></para></label-para>
    </para></subprov></prov.body></prov>
  <prov id="DLM6" toc="yes" deletion-status="repealed"><label>2</label><heading>Gone</heading>
   <prov.body/>
   <notes><history><history-note id="DLM7"><amended-provision>Section 2</amended-provision>:
    <amending-operation>repealed</amending-operation>, on <amendment-date>1 July 2020</amendment-date>,
    by <amending-provision href="DLM8" id="DLM9">section 5</amending-provision> of the
    <amending-leg>Amending Act 2019</amending-leg> (2019 No 7).</history-note></history></notes></prov>
  <part id="DLM10" toc="yes"><label>1</label><heading>Machinery</heading>
   <crosshead>Odds and ends</crosshead>
   <prov id="DLM11" toc="yes"><label>3A</label><heading>Later insertion</heading>
    <prov.body><para><text>Text of 3A.</text></para></prov.body></prov>
   <prov id="DLM12" toc="yes"><label>10</label><heading>Tenth</heading>
    <prov.body><para><text>Text of 10.</text></para></prov.body></prov></part>
 </body>
 <schedule.group>
  <schedule id="DLM13" prov-type="clause" toc="yes"><label>1</label>
   <heading>Implied covenants</heading>
   <empowering-prov><citation jurisdiction="nz"><intref href="DLM14" id="DLM15">s 3A</intref></citation></empowering-prov>
   <schedule.provisions>
    <part><label>1</label><heading>Land</heading>
     <prov id="DLM16"><label>1</label><heading>Payment</heading>
      <prov.body><para><text>Pay the money.</text></para></prov.body></prov></part>
    <part><label>2</label><heading>Goods</heading>
     <prov id="DLM17"><label>1</label><heading>Payment</heading>
      <prov.body><para><text>Pay the other money.</text></para></prov.body></prov></part>
   </schedule.provisions></schedule>
  <schedule id="DLM18" toc="yes"><label>2</label><heading>Enactments amended</heading>
   <schedule.amendments><para><text>Nothing much.</text></para></schedule.amendments></schedule>
 </schedule.group>
 <end><end.reprint-note><para><text>Reprint notes go here.</text></para></end.reprint-note></end>
</act>
"""

# The older DTD: no date.as.at, head4 headings, an enactment formula, a form.
OLD = b"""<?xml version="1.0" encoding="UTF-8"?>
<act act.no="4" act.type="public" date.as.at="" date.assent="1841-06-24"
     date.first.valid="1841-06-24" year="1841">
 <cover><title>Old Act 1841</title></cover>
 <front><long-title><para><text>An Act of some antiquity.</text></para></long-title>
  <enactment>BE IT ENACTED as follows:-</enactment></front>
 <body>
  <prov toc="yes"><label>1</label><heading>The first</heading>
   <prov.body><para><text>And be it enacted, That this is so. It is very much so.</text></para></prov.body></prov>
 </body>
 <schedule.group>
  <schedule><label>FIRST SCHEDULE</label><heading>Forms</heading>
   <schedule.forms><form><heading>FORMS</heading><form.body>
     <head4><label>No. 1</label><heading>General heading</heading></head4>
     <para><text>No.<field fill-length="10" fill="space"/>.</text></para>
     <signature-block><sig.officer>A. B.,</sig.officer><sig.para>Plaintiff.</sig.para></signature-block>
    </form.body></form></schedule.forms></schedule>
 </schedule.group>
</act>
"""

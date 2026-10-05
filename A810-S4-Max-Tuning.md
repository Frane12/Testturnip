# A810 S4 Max

Android ARM64 KGSL, minimalni Android API 34. Baza je potvrđeni S3 Orchestrator, Mesa commit `eda9aceb39d5ff169b096444abe366bdf2269e24`. Novi eksperimenti rade samo na A810. Sve metode iz tablice uključene su po defaultu.

## Nove metode i prekidači

| Varijabla | Default | Raspon / učinak |
| --- | ---: | --- |
| `TU_FRANE_GMEM_MULTISEED` | 1 | Četiri deterministička početna rasporeda: cpp/konflikti, broj konflikata, početak života, cpp × konflikti. Neaktivne, nepovezane živote može spojiti u track čiji je cpp maksimum članova. |
| `TU_FRANE_GMEM_SEEDS` | 4 | 1–4 početna rasporeda. Radi uz MULTISEED. |
| `TU_FRANE_GMEM_GAPS` | 1 | Pri jednakom trošku cpp-a preferira manje praznina u maski života tracka. Radi uz MULTISEED. |
| `TU_FRANE_GMEM_PEAK_BOUND` | 1 | Izračuna gornju granicu površine iz istodobno aktivnih attachmenta; zaustavi traženje kad raspored dostigne tu granicu. |
| `TU_FRANE_GMEM_BUDGET` | 16384 | 128–16384 čvorova uz postojeći pressure bound; bez njega maksimum 8192. S3 default bio je 4096 uz pressure bound. |
| `TU_FRANE_SCHED_WINDOW` | 1 | Novi red za texture/memory latency: pritisak registara <25/<45/<65/≥65% daje 6/4/3/2 uz zadani TEX_WINDOW. |
| `TU_FRANE_TEX_WINDOW` | 6 | 2–8; gornja granica SY reda. S3 default 4. |
| `TU_FRANE_SCHED_CRITICAL` | 1 | Među dopuštenim instrukcijama istog ready ranga pri malom pritisku prioritizira kritični put uz trošak rasta živih registara i udaljenost prve upotrebe. Pri ≥60% prioritizira najmanji rast. |
| `TU_FRANE_SCHED_SLACK` | 2 | 0–4; granica malog rasta za latency score je slack+1 skalarnih elemenata. Veći rast dobiva vrlo snažnu kaznu. Nije stvarna mjera occupancyja. |
| `TU_FRANE_SCHED_SFU` | 1 | Adaptivni SS red za SFU: pri <25/<45/<65/≥65% 6/5/3/2 uz zadani SFU_WINDOW. |
| `TU_FRANE_SFU_WINDOW` | 6 | 2–8; maksimum SFU reda, nikad iznad upstream granice 8. |

`TU_FRANE_SCHED=0` isključuje adaptivni shader scheduler kao u S3. Varijable učitati prije pokretanja procesa; nakon promjene ponovno pokrenuti igru/kontejner. Sve compiler postavke ulaze u novi shader cache ključ. Ne treba ručno brisati shader cache.

## Jači zadani profil

Četiri GMEM početna rasporeda, najveći dopušteni budget pretrage i sva tri scheduler eksperimenta aktivni su bez dodatnih varijabli. Texture prozor 6 ostavlja prostor za skrivanje latencije; pressure ladder ga smanjuje pri većoj procjeni živih registara. Broj 8 ostaje moguć za A/B, ali nije tvrdnja da bi svugdje bio brži.

Ovo je IR3 shader scheduler. KGSL/kernel redovi, GPU clock i hardverski cache kapaciteti nisu novi eksperimenti ovog builda. S3 paired controller, smart CB i postojeće metode ostaju na svojim potvrđenim defaultima. Nove GMEM metode rade pri stvaranju render passa, samo za mask allocator s 3–16 stavki i najviše 64 subpassa; običan pass s jednim subpassom od njih ne dobiva korist.

Raspored se prihvaća samo ako povećava točnu kapacitetnu površinu. Provjera koristi prijavljeni GMEM, stvarno poravnanje i nepreklapajuće životne maske. Finalni GMEM safety gate, LRZ provjere, overflow i BV/BR čekanja ostaju. A810 CCU ostaje SYSMEM color/depth 64/64 KiB, GMEM color/depth 32/48 KiB i potvrđene frakcije FULL/THREE_QUARTER/EIGHTH/FULL.

## Usporedba sa S3 ponašanjem

Za ponašanje novog koda kao S3 postaviti sljedeće, uz inače iste postavke:

```text
TU_FRANE_GMEM_MULTISEED=0
TU_FRANE_GMEM_PEAK_BOUND=0
TU_FRANE_GMEM_GAPS=0
TU_FRANE_GMEM_BUDGET=4096
TU_FRANE_SCHED_WINDOW=0
TU_FRANE_SCHED_CRITICAL=0
TU_FRANE_SCHED_SFU=0
TU_FRANE_TEX_WINDOW=4
```

Za najčišću usporedbu koristi i originalni S3 ZIP. Ako se pojavi lošiji frame pacing, prvo usporedi `TU_FRANE_SCHED_CRITICAL=0`, zatim `TU_FRANE_SCHED_SFU=0`, pa `TU_FRANE_TEX_WINDOW=4`. Svaku opciju mijenjati zasebno. DXVK i ostale postavke držati jednakima. Procijeniti 3 Crysis prolaza i 2–3 Dirt vožnje, zagrijano stanje, prosječni FPS, trzaje i render.

## Provjera i ograničenja

Test kompilira funkcije iz stvarnog izmijenjenog `tu_pass.cc`, uključujući postojeći DFS, exact packing i nove metode. 16.000 generiranih passova provjerava kapacitet, maske, assignment, alignment, granicu memorije i rezultat prema S3 pri jednakom search budgetu. Manji slučajevi uspoređuju peak bound i rezultat s iscrpnim optimumom. Scheduler test provjerava pressure ladder, ograničenja reda i rast registara u scoreu. CI ponavlja test pod UBSan i ASan+UBSan, regresiju S3 controllera te kompajlira Android ARM64 biblioteku.

To nisu GPU mjerenja ni Vulkan CTS. Sintetička GMEM dobit ne predviđa FPS u igri; shader ordering i cijeli driver zahtijevaju provjeru na uređaju. S3 driver je korisnik potvrdio, S4 je eksperimentalan.

Prethodne S3 opcije opisane su u `A810-S3-Orchestrator-Tuning.md` unutar source ZIP-a.

Osnova za razliku GMEM/SYSMEM i mjereni autotune: [Mesa Freedreno dokumentacija](https://docs.mesa3d.org/drivers/freedreno.html). Nove heuristike su lokalni eksperimenti, nisu službene A810 preporuke.

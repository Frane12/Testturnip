# Turnip-Drnas A810 S3 Orchestrator — upravljanje eksperimentom

Ovaj ZIP sadrži stvarni Android ARM64 driver. Baza je S2.1 koji je Frane
potvrdio kao ispravan nakon povrata naših CCU postavki. S3 je zaseban interni
eksperiment; dobitak na uređaju još nije izmjeren.

## Prvi test

Instaliraj A810-S3-Orchestrator.zip i prvo probaj bez novih varijabli.
TU_AUTOTUNE_ALGO=profiled zadrži kao u S2.1. Zadrži isti DXVK, FEX,
rezoluciju, affinity, postavke igre i način hlađenja.
Za standardnu usporedbu koristimo DXVK 1.9.4; ako trenutačno provjeravaš drugu
verziju, zadrži je u oba drivera. Nakon provjere slike usporedi tri Crysis passa
i nekoliko minuta borbi/vožnje. Gledaj prosjek, padove i fluidnost cijelog rada.

Promijeni jednu skupinu postavki odjednom i ponovno pokreni igru/kontejner.
Varijable se čitaju jednom pri inicijalizaciji, nisu prekidači usred igre.

## Tri režima

| Režim | Varijabla | Namjera i cijena |
|---|---|---|
| Uravnoteženi | TU_FRANE_ORCH_POLICY=1 | Zadano. Učenje iz svježih parova, umjerena kazna nestabilnosti, rijetki kontrolni uzorci. |
| Propusnost | TU_FRANE_ORCH_POLICY=2 | Manje mjerenja nakon stabilizacije, četiri početna para, slabija kazna nestabilnosti; promjene može primijetiti kasnije. |
| Fluidnost | TU_FRANE_ORCH_POLICY=3 | Više provjera, osam početnih parova i veća kazna nestabilnosti; može smanjiti vršni FPS zbog dodatnog profiliranja. |
| S2.1 put odlučivanja | TU_FRANE_ORCH=0 | Isključuje novi upravljač. Za usporedbu zadanih buildova ukloni i sve opcionalne shader/CB override varijable. |

Ne treba upisati sve varijable. TU_FRANE_ORCH je zadano 1, a policy zadano 1.
TU_FRANE_SMART=0, isključen GMEM runtime, isključen GMEM turbo ili izostanak
PROFILED one-time puta također sprječavaju uključivanje novog upravljača.

## Novi upravljač

Brojevi se odnose na ponavljanja istog obrasca render-passa, ne na cijele
frameove. Jedan frame može sadržavati mnogo obrazaca. Svaki obrazac ima zasebnu
povijest u već postojećoj tablici. Stanje se ne sprema u novi disk-cache.

| Varijabla | Zadano balanced | Raspon | Ponašanje |
|---|---:|---|---|
| TU_FRANE_ORCH | 1 | 0/1 | Glavni prekidač novog upravljača. |
| TU_FRANE_ORCH_POLICY | 1 | 0–3 | 0 isključuje; 1 balanced; 2 throughput; 3 fluidity. |
| TU_FRANE_ORCH_COLD_LOG2 | 4 | 3–6 | Dva susjedna izmjerena prolaza u svakom bloku od 2^N ponavljanja dok se uči. |
| TU_FRANE_ORCH_WARM_LOG2 | 6 | cold–9 | Razmak parova nakon prve pouzdane odluke. |
| TU_FRANE_ORCH_HOT_LOG2 | 9 | warm–10 | Razmak parova za stabilnu povijest. 9 znači blok od 512 ponavljanja, 10 od 1024. |
| TU_FRANE_ORCH_SENTINEL_LOG2 | 8 | 4–10 | Jedan kontrolni uzorak pobjednika po bloku od 2^N; preklapanje s parom ne stvara dodatni uzorak. |
| TU_FRANE_ORCH_MIN_PAIRS | 6 | 4–16 | Najmanje svježih parova prije zadržavanja izmjerenog pobjednika. |
| TU_FRANE_ORCH_GAIN | 25 | 5–250 | Donja granica prednosti u promilima većeg troška. 25 znači 2,5%; uz nju se dodaje kazna nestabilnosti. |
| TU_FRANE_ORCH_RISK | 100 | 0–400 | Težina prosječnog apsolutnog odstupanja. 100 znači jednu takvu kaznu; 0 uklanja kaznu. |
| TU_FRANE_ORCH_EMA_SHIFT | 2 | 1–5 | Novi par ažurira prosjek udjelom 1/2^N. Manje brže reagira, veće dulje pamti. |
| TU_FRANE_ORCH_DRIFT | 300 | 100–1000 | Promjena trajanja kontrolnog uzorka podijeljena većim od starog i novog trajanja, u promilima. |
| TU_FRANE_ORCH_DRIFT_HITS | 2 | 1–4 | Uzastopnih velikih promjena prije ponovnog učenja. |
| TU_FRANE_ORCH_MAX_AGE | 2048 | najmanje 2×hot blok; najviše 65536 | Stara povijest prestaje držati odluku dok ne dobije svježe parove. |
| TU_FRANE_ORCH_MAX_TILES | 64 | 8–128 | Najviše procijenjenih pločica za novi upravljač. Završna GMEM provjera uvijek vrijedi. |
| TU_FRANE_ORCH_MIN_US | 8 | 0–1000 | Obrasci čija su oba izmjerena puta kraća od praga ne dobivaju zaključanu odluku; provjeravaju se rijetkim parovima. |
| TU_FRANE_ORCH_LOG | 0 | 0/1 | DRNAS_ORCH zapis: parovi, pobjednik, pouzdanost, prednost, odstupanje i broj ponovnih učenja. Upali samo za dijagnostiku. |

Preset 2 mijenja hot=10, sentinel=9, min_pairs=4, gain=15, risk=50.
Preset 3 mijenja cold=3, hot=8, sentinel=6, min_pairs=8, gain=40, risk=150.
Izričite varijable imaju prednost nad presetom; međusobno neusklađeni razmaci
normaliziraju se tako da cold <= warm <= hot. Depth/load-store rizični prolazi
koriste za jedan stupanj češće parove. Raspored mjesta unutar bloka mijenja se
kako mjerenje ne bi stalno pogađalo istu fazu cikličke scene.

## Concurrent binning

| Varijabla | Zadano | Raspon | Ponašanje |
|---|---:|---|---|
| TU_FRANE_SMART_CB | 1 | 0/1 | Postojeći glavni CB1 prekidač. TU_DEBUG=nocb ostaje autoritativan. |
| TU_FRANE_SMART_CB_MODE | 1 | 0–5 | 0 GPU feedback bez prisilnog zadržavanja; 1 postojeći CB1; 2–4 starije reference; 5 nova konfigurabilna keep vrata. |
| TU_FRANE_CB_BIAS | 0 | −4–8 | Pomak praga broja drawova za prijam CB-a. Negativno dopušta više pokušaja; GPU feedback ostaje. |
| TU_FRANE_CB_KEEP_DRAWS | 28 | 16–128 | Minimalni drawovi za keep u modu 5. |
| TU_FRANE_CB_KEEP_TILES | 12 | 4–64 | Minimalne pločice za keep u modu 5. |
| TU_FRANE_CB_KEEP_BW | 16 | 8–64 | Minimalni postojeći bandwidth-per-sample pokazatelj za keep u modu 5. |

Za umjeren zaseban CB eksperiment uz default controller probaj samo
TU_FRANE_CB_BIAS=-1. Mode 5 primjenjuje sva tri keep uvjeta zajedno;
može zaobići performance-only automatsko gašenje CB-a i zato traži zaseban A/B.
GPU wait, overflow i sinkronizacijske provjere ostaju aktivne.

## Shader i scheduler kontrole

Ovo su novi TU_FRANE nazivi za stvarne postojeće A810 metode u compileru.
Zadane vrijednosti odgovaraju S2.1. Stari TU_A810 nazivi i dalje su fallback;
ako postoji novi naziv, on ima prednost. Efektivne postavke sudjeluju u ključu
shader-cachea, pa promjena može pokrenuti novo kompajliranje shadera.

| Varijabla | Zadano | Raspon |
|---|---:|---|
| TU_FRANE_TEX_WINDOW | 4 | 2–8; signed clamp |
| TU_FRANE_SCHED | 1 | 0/1; adaptive pressure-aware scheduler |
| TU_FRANE_UBO_GAP | 64 | 0, 32, 64, 128; ostalo vraća 64 |
| TU_FRANE_TEX_PREFETCH | 1 | 0/1; glavni guarded texture prefetch |
| TU_FRANE_PREFETCH_DUAL | 1 | 0/1 |
| TU_FRANE_PREFETCH_TRIPLE | 1 | 0/1 |
| TU_FRANE_PREFETCH_QUAD | 1 | 0/1 |
| TU_FRANE_PREFETCH_DIVERSITY | 1 | 0/1 |
| TU_FRANE_PREFETCH_SCORE | 0 | 0/1; postojeći eksperimentalni selektor |

Za zaseban shader eksperiment možeš probati TU_FRANE_TEX_WINDOW=5 uz sve
ostalo isto. Veći prozor ne jamči više FPS-a: može podići register pressure.
Kontrole pojedinih prefetch stupnjeva vrijede unutar postojećih shader gateova;
uključivanje opcije ne znači da je svaki shader ili svaki stupanj dopušten.

## Što smo zadržali

CCU: SYSMEM color/depth 64/64 KiB; GMEM color/depth 32/48 KiB i naše
postojeće cache fractions. Nema povećanja fizičke memorije niti proizvoljnih
novih attachment offseta. GMEM allocator, LRZ, GPU waits i KGSL politika su
ista baza kao u S2.1. Upravljač je ograničen na A810, eligible PROFILED
one-time passove, do 1920×1080 ukupnih pass-pixela i postojeće završne provjere.

## Dokaz i granica testa

UBSan i ASan/UBSan prošli su tagged-pair reorder/duplicate/stale testove,
rollover, UINT64_MAX trajanja, šum, male prolaze, promjenu troška, konfiguracijske
granice, layout granice i 400000 fuzzed parova. Simulacija balanced režima:
156 mjerenja na 19999 stabilnih ponavljanja; preokret troška na ponavljanju
25000 prepoznat na 25185. To nisu izmjereni FPS rezultati na Androidu.
Stvarni dobitak i ispravnost novog builda potvrđujemo na tvojem A810.


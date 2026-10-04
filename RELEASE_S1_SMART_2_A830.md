# A830 S1 Smart Performance 2

A830 varijanta za smart processing performance mode. Android ARM64 driver je stvarno kompajliran iz A830 RC1 stacka; nije preimenovani A810 binarni driver. Nema power-max podešavanja, novih frekvencija ni pretpostavke da više sistemskog RAM-a povećava fizički GMEM.

## Zadano ponašanje i page fault

**Zadano SYSMEM.** Najnoviji pregledani whitebelyash Mainline Turnip v32 (19. rujna 2026.) još prijavljuje A830 GMEM write page fault. Nisam pronašao primjenjiv, provjeren fix koji bi dopustio proglašavanje našeg A830 GMEM-a sigurnim. Zato se na A830 odabir zaustavlja prije autotunera i GMEM debug overridea: nema probnog GMEM izvršavanja, GMEM/SYSMEM RNG-a ni timestamp mjerenja tog odabira.

`TU_FRANE_A830_GMEM=1` izričito uključuje **eksperimentalni** GMEM i punu Smart povijest; to nije potvrđen page-fault fix. `TU_FRANE_SMART=0` gasi novu memoriju odluka, ali ne uklanja sigurnosnu karantenu. `TU_DEBUG=sysmem` uvijek ostaje prisilni SYSMEM.

Probni GMEM dopušta samo jedan layer/view, bez FDM, MSRTSS, MSAA i resolve putanja. Provjerava fizički i usable GMEM, maksimalne tile piksele, offset i kraj svakog GMEM attachmenta, uključujući zaseban D32S8 stencil. Sumnjiv prolaz vraća se u SYSMEM. Rezervacije CCU/VPC cachea provjeravaju se prije unsigned oduzimanja; nevaljana konfiguracija odbija inicijalizaciju umjesto emitiranja pogrešnih adresa. To štiti pregledane granice, ali ne dokazuje ispravnost hardverskog GMEM programiranja.

## Memorija scene — ista politika kao A810 Smart 2

| Stanje | Dokaz | Ponašanje i mjerenje |
|---|---|---|
| COLD | nedovoljno ili zastarjelo upareno iskustvo | jedna kontrolna GMEM/SYSMEM para u bloku od 8 ponavljanja; ostalo osnovni selector |
| WARM | confidence najmanje 4/8, najmanje 8 svježih parova | memorirani pobjednik; 2 mjerenja u 64 ponavljanja |
| TRUSTED | confidence najmanje 6/8, najmanje 12 parova | 2 mjerenja u 128 ponavljanja |
| LOCKED | confidence 8/8, najmanje 16 parova | 2 mjerenja u 256 ponavljanja |

Tablica vrijedi za probni GMEM i legalne PROFILED jednokratne command buffere. Zadana karantena ima prednost nad svim tierovima. Dva mjerenja su susjedni pobjednik/gubitnik, s promjenjivim determinističkim položajem po bloku. Par smije glasati samo ako oba nova uzorka pripadaju istom render obrascu i udaljena su najviše 8 pojavljivanja; stari uzorak ne glasa ponovno. Confidence je ponderirana ocjena slaganja, nije statistička vjerojatnost. Dvije jake suprotne pare poništavaju staru prednost, nestabilnost spušta tier, a povijest bez novog para istječe nakon 512 pojavljivanja. Veliki ili depth/stencil load/store prolazi traže barem TRUSTED. Snažan suprotan PROFILED signal vraća osnovnom učenju.

Odluka i zahtjev za mjerenje imaju jednog vlasnika. Memorirani odgovor izlazi prije RNG-a, legacy boosta i measurement ticketa. Nema novih alokacija, satova, mutexa ni čekanja u samom Smart helperu. Jedna dodatna atomska occurrence oznaka pripada jednom render obrascu; pakirana povijest objavljuje se atomskim 64-bitnim snapshotom.

## Prenesene Mesa ispravke

- `a995eaeda4339adb0278b06dcc98136011feac36`: CmdClearAttachments bilježi GMEM blit-write pristup/barijeru.
- `d498e0830b62d0a07983c8f9fbc361701526f3f1`: nedostajući munmap u KGSL fixed-address neuspjehu.
- `90b7cff158f7ab576d2d43bb98e1f5fc2f0b2e64`: ION handle/fd cleanup pri neuspjeloj alokaciji.
- `c4aa23ef9c74ad02383834843ac31560f13ec3df`: KGSL dma-buf import cleanup kad GPUOBJ_INFO ne uspije.

Noviji `cfc8789c` suballoc NULL fix već je pokriven našim postojećim stackom. Zadržana je A830 V59 LRZ-CLEAN logika. Neprovjerene community promjene za 64KB shared memory, A810/A825/A829 cache parametre, gašenje sample interpolationa i FDM shader semantike nisu prenesene. Jedan community GPU uvjet sadrži `id == ... || 0x44050001`, što je uvijek istinito; naš gate uspoređuje sve četiri A830 oznake zasebno. Stari p33k-a-b00 GMEM-offset patch već je prisutan u našoj bazi i nije novi A830 fault fix. Faux123 javni repo nema izvor njegovih privatnih pratećih patcheva za prijavljene device rezultate.

Pregledano stanje upstream main: `e5f0687867f5c5e88619175d9b0442f8560e8d53` (3. listopada). Reproducibilna baza: `eeca16aa41e89a114e53e76439df623c7efb9519`, A830 RC1 stack `e40ce9d479448900c1a28e9d69561c207d0832e3`.

## Testovi — stvarno izvršeno

- **716.040 kombinacija Smart politike:** confidence, broj parova, PROFILED granice, tail-risk, nestabilnost i oba pobjednika.
- Svježina parova, odbacivanje starog/reupotrijebljenog uzorka, obrnuti redoslijed dovršavanja, uint32 rollover, ties, saturacija i UINT64_MAX.
- Točna kadenca, promjena položaja probe kroz 128 blokova, izbjegavanje fiksne faze.
- Sintetska promjena pobjednika u pojavljivanju 4096: novi TRUSTED pobjednik u 4335; 135 zahtjeva za mjerenje u 10.000 ponavljanja. Ovo je model, ne FPS test.
- **830 slučajeva A830 aritmetike** s nezavisnim 128-bitnim oracleom: GPU gate, cache rezervacije, attachment/stencil raspon, nula, negativni offset i ekstremni overflow.
- **ASan i UBSan prošli**, bez prijavljenih grešaka; leak detector isključen zbog ograničenja host okruženja.
- Izvorne provjere redoslijeda sigurnosnih gateova, scope ograničenja, ranog Smart izlaza i KGSL cleanupa.
- **Android ARM64 NDK r29 release build prošao** svih 896 build koraka. ZIP integritet, ELF64 AArch64, identitet, runtime opcije i Android shared-library ovisnosti provjereni.

Nije izvršeno: A830 GPU/game test, Vulkan CTS na uređaju, mjerenje FPS-a/temperature/energije ili potvrda odsutnosti page faulta na hardveru. Ne tvrdim da su CPU model ili uspješan build zamjena za te testove.

## Izvori

- https://github.com/whitebelyash/AdrenoToolsDrivers/releases/tag/tu_v32
- https://github.com/whitebelyash/mesa-unified/tree/turnip/gen8
- https://github.com/p33k-a-b00/mesa-turnip-a830/commit/d73dcf59402a35d344b24539501f926cb27bf7fe
- https://github.com/faux123/faux123-Adreno-Turnip-Drivers
- https://github.com/chaotic-cx/mesa-mirror

AI provenance: Generated-by: LLM. biblioklept

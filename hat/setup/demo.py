"""Demo data for the HAT marketplace: distributors, hotels, listings, partnerships and ratings.

Company and hotel names are fictional; places, products and price levels follow the Albanian
HoReCa market (wholesale, ALL, excluding VAT, October 2026). Products are ERPNext Items
(HAT-FB-0001, ...) shared by every distributor that sells them (COMPETING_OFFERS). Safe to run repeatedly: listings and items are
updated in place, and listings dropped from LISTINGS are removed.

	bench --site <site> execute hat.setup.demo.create_demo
	bench --site <site> execute hat.setup.demo.delete_demo
"""

import re
from functools import cache

import frappe
from frappe.utils import add_days, today

from hat.hospitality_and_tourism_academy.doctype.hat_listing.hat_listing import next_item_code
from hat.setup.catalogue import CATALOGUE, CATEGORY_CODES

DEMO_PASSWORD = "HatDemo2026!"
EXTRA_UOMS = ("Bottle", "Pack", "Crate", "Month")
LISTING_NOTE = "<p>Çmim shumice për njësi, pa TVSH. Dërgesa sipas kushteve të shpërndarësit.</p>"

FOOD = "Ushqim & Pije"
KITCHEN = "Pajisje Kuzhine, Enë & Shërbim Restoranti"
ROOMS = "Mobilje, Tekstile & Akomodim"
TECH = "Teknologji, Harduer & Softuer ERP-POS"
SERVICES = "Shërbime Profesionale, Projektim & Konsulencë"
DEMO_ITEM_PREFIX = "HAT-"
ALL_COUNTIES = None  # no coverage listed = delivers everywhere by agreement


# Product icons: a Lucide icon (shipped with Frappe, ISC licence) on a tile tinted by category.
ICON_FILE_PREFIX = "hat-icon-"
# top category code: (background from, background to, icon colour)
ICON_COLOURS = {
	"FB": ("#FFF4E5", "#FFDDB0", "#C2410C"),
	"KT": ("#EAF2FB", "#CADDF5", "#1D4ED8"),
	"RM": ("#E8F6F1", "#C3EAD9", "#047857"),
	"TC": ("#EEF0FD", "#D3D8FA", "#4338CA"),
	"SV": ("#F5EDFB", "#E5D0F6", "#7E22CE"),
}
GROUP_ICONS = {
	"Pije me Alkool të Lartë": "martini",
	"Vera & Shampanjë": "wine",
	"Birra": "beer",
	"Pije Jo-Alkoolike": "cup-soda",
	"Kafe": "coffee",
	"Çajra": "leaf",
	"Shurupë & Pure": "droplets",
	"Acesorë Pijesh": "candy",
	"Mish & Shpendë": "beef",
	"Peshk & Meze Deti": "fish",
	"Brumëra & Bukë": "croissant",
	"Fruta & Perime": "carrot",
	"Bulmet & Vezë": "milk",
	"Ushqime të Thata & Salca": "wheat",
	"Desserts & Ëmbëlsira": "ice-cream-cone",
	"Produkte të Egra, Artizanale & Fshati": "sprout",
	"Produkte Premium nga e Gjithë Bota": "gem",
	"Furra & Skara": "flame",
	"Frigoriferë & Prodhues Akulli": "refrigerator",
	"Sous-Vide & Vakum": "package",
	"Larëse Industriale": "washing-machine",
	"Tenxhere, Tigaie & Tava GN": "cooking-pot",
	"Thika & Vegla Prerëse": "slice",
	"Chafing Dishes & Bufete": "hand-platter",
	"Termusë & Dispensers": "coffee",
	"Karroca Industriale": "luggage",
	"Porcelan & Pjata": "utensils",
	"Gota & Shishe": "wine",
	"Servise": "utensils-crossed",
	"Uniforma Stafi": "shirt",
	"Tekstile Dhome & Fjetje": "bed-double",
	"Tekstile Banjoje": "bath",
	"Tekstile Restoranti": "utensils",
	"Dyshekë & Mbrojtës": "bed",
	"Jastëkë & Jorgane": "bed",
	"Mobilje Dhome & Akomodimi": "lamp-desk",
	"Divane & Ndenjëse": "sofa",
	"Mobilje Restoranti & Bari": "armchair",
	"Produkte Higjienike": "shower-head",
	"Pajisje Elektrike Dhome": "plug",
	"Kimikate & Detergjente": "spray-can",
	"Produkte Letre": "scroll",
	"Mjete Pastrimi": "brush",
	"Lavanteri, Pastrim & Kopshtari": "washing-machine",
	"Pikë Shitjeje (POS)": "monitor",
	"Pajisje Akomodimi": "key-round",
	"Rrjeti & Siguria": "wifi",
	"Sisteme Menaxhimi": "laptop",
	"Module Integrimi": "plug",
	"Projektim Arkitektural & Interior Design": "drafting-compass",
	"Projektim Teknologjik Kuzhine-Bari": "chef-hat",
	"Projektim & Realizim": "waves-ladder",
	"Mystery Shopper & Auditim Shërbimi": "clipboard-check",
	"Çertifikime Standardesh": "badge-check",
	"Shërbime Sigurie": "shield",
	"Punime & Mirëmbajtje Elektrike": "zap",
	"Konsulencë Operacionale HoReCa": "briefcase",
	"Menaxhim Operacional": "hotel",
	"Trajnim Stafi": "graduation-cap",
	"Shërbime Marketingu": "megaphone",
	"Rezervo Artistin": "music",
	"Organizim Eventesh & Floristë": "party-popper",
	"Qira Pajisjesh": "speaker",
}
# A word in the product name picks a closer icon than its group's (first match wins)
NAME_ICONS = [
	("ujë", "glass-water"),
	("lëng", "citrus"),
	("prosecco", "wine"),
	("mollë", "apple"),
	("portokall", "citrus"),
	("limon", "citrus"),
	("domate", "cherry"),
	("sallatë", "salad"),
	("pule", "drumstick"),
	("pulë", "drumstick"),
	("midhje", "shell"),
	("karkaleca", "shell"),
	("kallamar", "shell"),
	("oktapod", "shell"),
	("salmon", "fish"),
	("vezë", "egg"),
	("pice", "pizza"),
	("akullore", "ice-cream-cone"),
	("vaj ", "droplets"),
	("salcë", "soup"),
	("mjaltë", "flower"),
	("reçel", "cherry"),
	("gështenja", "bean"),
	("parmigiano", "crown"),
	("shafran", "flower"),
	("friteuzë", "flame"),
	("akulli", "snowflake"),
	("frigoriferike", "snowflake"),
	("printer", "printer"),
	("sirtar", "credit-card"),
	("karta", "credit-card"),
	("bravë", "lock-keyhole"),
	("lexues", "scan-line"),
	("kamerë", "cctv"),
	("fiskal", "scan-line"),
	("channel", "store"),
	("pishin", "waves-ladder"),
	("roje", "shield"),
	("fotografi", "camera"),
	("video", "camera"),
	("dj për", "speaker"),
	("lule", "flower"),
	("projektor", "projector"),
	("kopsht", "trees"),
	("fasade", "sparkles"),
	("minibar", "refrigerator"),
	("kasafortë", "lock-keyhole"),
	("kazan", "coffee"),
	("tharëse", "heater"),
	("shtrat", "bed"),
	("rrobë banje", "shirt"),
	("këpucë", "shirt"),
	("leckë", "sparkles"),
	("housekeeping", "trash-2"),
]

# name: (city, categories, coverage, minimum order)
DISTRIBUTORS = {
	"Pije Shqiptare Distribution sh.p.k.": (
		"Tiranë",
		[FOOD],
		["Tiranë", "Durrës", "Elbasan", "Fier", "Vlorë", "Berat", "Korçë", "Shkodër", "Lezhë"],
		15000,
	),
	"Agro Freskia sh.p.k.": (
		"Fier",
		[FOOD],
		["Fier", "Vlorë", "Durrës", "Tiranë", "Berat", "Elbasan"],
		10000,
	),
	"Deti Jon Seafood sh.p.k.": ("Vlorë", [FOOD], ["Vlorë", "Fier", "Gjirokastër", "Durrës"], 8000),
	"Bio Malësia sh.p.k.": ("Shkodër", [FOOD], ["Shkodër", "Lezhë", "Tiranë", "Kukës", "Dibër"], 5000),
	"Gourmet Import Albania sh.p.k.": ("Tiranë", [FOOD], ALL_COUNTIES, 20000),
	"HoReCa Pajisje sh.p.k.": ("Tiranë", [KITCHEN], ALL_COUNTIES, 0),
	"Tekstil Hotel Korça sh.p.k.": ("Korçë", [ROOMS], ALL_COUNTIES, 25000),
	"Pastërti Pro sh.p.k.": (
		"Durrës",
		[ROOMS],
		["Durrës", "Tiranë", "Lezhë", "Fier", "Vlorë", "Elbasan"],
		8000,
	),
	"Mobilieri Adriatik sh.p.k.": ("Durrës", [ROOMS], ALL_COUNTIES, 50000),
	"Smart HoReCa Tech sh.p.k.": ("Tiranë", [TECH], ALL_COUNTIES, 0),
	"Mikpritja Consulting sh.p.k.": ("Tiranë", [SERVICES], ALL_COUNTIES, 0),
	"Eventi Shqip sh.p.k.": ("Tiranë", [SERVICES], ["Tiranë", "Durrës", "Elbasan", "Shkodër", "Vlorë"], 0),
	# Competitors: they sell products already in the catalogue (see COMPETING_OFFERS)
	"Bevera Jug sh.p.k.": ("Vlorë", [FOOD], ["Vlorë", "Fier", "Gjirokastër", "Berat"], 12000),
	"Cash & Carry Tirana sh.p.k.": ("Tiranë", [FOOD, ROOMS], ["Tiranë", "Durrës", "Elbasan"], 10000),
	"Tregu Fresk Tirana sh.p.k.": ("Tiranë", [FOOD], ["Tiranë", "Durrës", "Elbasan", "Dibër"], 6000),
	"Peshku i Durrësit sh.p.k.": ("Durrës", [FOOD], ["Durrës", "Tiranë", "Lezhë", "Elbasan"], 8000),
	"Gastro Equipment Albania sh.p.k.": ("Durrës", [KITCHEN], ALL_COUNTIES, 0),
	"Linen Hotel Durrës sh.p.k.": ("Durrës", [ROOMS], ALL_COUNTIES, 20000),
	"Fiskal Tech sh.p.k.": ("Tiranë", [TECH], ALL_COUNTIES, 0),
}

# name: (county, city, stars, type, rooms, latitude, longitude)
HOTELS = {
	"Grand Hotel Bulevardi": ("Tiranë", "Tiranë", "5", "Hotel", 120, 41.3231, 19.8211),
	"Hotel Skanderbeg Square Inn": ("Tiranë", "Tiranë", "4", "Hotel", 64, 41.3289, 19.8178),
	"Resort Gjiri i Lalzit": ("Durrës", "Durrës", "5", "Resort", 210, 41.4389, 19.4772),
	"Hotel Plazhi i Durrësit": ("Durrës", "Durrës", "4", "Hotel", 85, 41.3123, 19.4560),
	"Hotel Riviera Vlorë": ("Vlorë", "Vlorë", "4", "Hotel", 72, 40.4520, 19.4870),
	"Dhërmi Bay Resort": ("Vlorë", "Dhërmi", "5", "Resort", 150, 40.1530, 19.6400),
	"Ksamil Blue Boutique": ("Vlorë", "Ksamil", "3", "Boutique Hotel", 22, 39.7690, 20.0010),
	"Hotel Kalaja Gjirokastër": ("Gjirokastër", "Gjirokastër", "3", "Boutique Hotel", 16, 40.0758, 20.1389),
	"Hotel Mangalemi i Ri": ("Berat", "Berat", "3", "Boutique Hotel", 24, 40.7058, 19.9522),
	"Hotel Liqeni Shkodër": ("Shkodër", "Shkodër", "4", "Hotel", 58, 42.0683, 19.5126),
	"Bujtina Theth Alpine": ("Shkodër", "Theth", "", "Apartments", 12, 42.3956, 19.7744),
	"Hotel Pogradeci Liqen": ("Korçë", "Pogradec", "4", "Hotel", 66, 40.9025, 20.6525),
	"Restorant Rrapi Korçë": ("Korçë", "Korçë", "", "Restaurant", 0, 40.6186, 20.7808),
}

# distributor: [(item group, title, uom, price or None for price on request, minimum qty, lead days)]
# Wholesale prices per unit in ALL, excluding VAT (pa TVSH). Calibrated October 2026 against retail
# prices in Tirana (Numbeo, Big Market / Wolt, press reports) less the usual 15-30% HoReCa margin;
# equipment from EU dealer prices at ~97 ALL/EUR.
LISTINGS = {
	"Pije Shqiptare Distribution sh.p.k.": [
		("Birra", "Birra Tirana 0.33 L shishe kthyese, arkë 24 copë", "Crate", 1850, 5, 2),
		("Birra", "Birra Tirana 0.5 L kanoçe, pako 24 copë", "Pack", 2250, 5, 2),
		("Birra", "Birra Korça 0.5 L kanoçe, pako 24 copë", "Pack", 2300, 5, 2),
		("Birra", "Birra Korça e Zezë 0.33 L shishe, arkë 24 copë", "Crate", 2350, 3, 2),
		("Birra", "Birra Stela 0.33 L shishe, arkë 24 copë", "Crate", 1750, 5, 2),
		("Birra", "Birra Tirana fuçi 30 L (birrë e hapur)", "Unit", 6200, 2, 3),
		("Birra", "Heineken 0.33 L shishe, arkë 24 copë", "Crate", 2950, 3, 3),
		("Pije Jo-Alkoolike", "Ujë Tepelena 0.5 L, pako 12 copë", "Pack", 360, 20, 1),
		("Pije Jo-Alkoolike", "Ujë Tepelena 1.5 L, pako 6 copë", "Pack", 270, 20, 1),
		("Pije Jo-Alkoolike", "Ujë Glina 0.33 L xhami (restorant), arkë 24 copë", "Crate", 1150, 5, 2),
		("Pije Jo-Alkoolike", "Ujë Lajthiza i gazuar 0.25 L xhami, arkë 24 copë", "Crate", 1300, 5, 2),
		("Pije Jo-Alkoolike", "Coca-Cola 0.25 L xhami, arkë 24 copë", "Crate", 1700, 5, 2),
		("Pije Jo-Alkoolike", "Coca-Cola 0.33 L kanoçe, pako 24 copë", "Pack", 1800, 5, 2),
		("Pije Jo-Alkoolike", "Lëng frutash 100% 1 L tetrapak (portokall), pako 12", "Pack", 2100, 3, 2),
		("Pije Jo-Alkoolike", "Red Bull 0.25 L kanoçe, pako 24 copë", "Pack", 3850, 2, 3),
		("Pije me Alkool të Lartë", "Raki rrushi Skrapar 40% 0.7 L", "Bottle", 650, 6, 3),
		("Pije me Alkool të Lartë", "Konjak Skënderbeu 40% 0.7 L", "Bottle", 760, 6, 3),
		("Pije me Alkool të Lartë", "Whisky Johnnie Walker Red Label 0.7 L", "Bottle", 1550, 6, 3),
		("Pije me Alkool të Lartë", "Whisky Jameson 0.7 L", "Bottle", 1750, 6, 3),
		("Pije me Alkool të Lartë", "Vodka Absolut 0.7 L", "Bottle", 1450, 6, 3),
		("Pije me Alkool të Lartë", "Gin Gordon's London Dry 0.7 L", "Bottle", 1300, 6, 3),
		("Pije me Alkool të Lartë", "Aperol 1 L", "Bottle", 1450, 6, 3),
		("Vera & Shampanjë", "Verë e kuqe Kallmet 0.75 L (kantinë shqiptare)", "Bottle", 1050, 6, 3),
		("Vera & Shampanjë", "Verë e bardhë Shesh i Bardhë 0.75 L", "Bottle", 450, 6, 3),
		("Vera & Shampanjë", "Verë e kuqe Shesh i Zi 0.75 L", "Bottle", 480, 6, 3),
		("Vera & Shampanjë", "Verë shtëpie e kuqe bag-in-box 5 L", "Unit", 1900, 2, 3),
		("Vera & Shampanjë", "Prosecco DOC Extra Dry 0.75 L", "Bottle", 900, 6, 3),
		("Kafe", "Kafe espresso kokërr Lavazza Super Crema 1 kg", "Pack", 2600, 4, 2),
		("Kafe", "Kafe espresso kokërr, blend bari (pjekës vendas) 1 kg", "Pack", 1900, 5, 2),
		("Kafe", "Kafe turke e bluar 500 g", "Pack", 650, 10, 2),
		("Çajra", "Çaj mali i Shqipërisë (sideritis) 50 g", "Pack", 220, 10, 2),
		("Çajra", "Çaj Lipton Yellow Label, kuti 100 qeska", "Box", 1150, 5, 2),
		("Shurupë & Pure", "Shurup Monin karamel 0.7 L", "Bottle", 1150, 3, 3),
		("Shurupë & Pure", "Pure luleshtrydhe për kokteje 1 L", "Bottle", 1350, 3, 3),
		("Acesorë Pijesh", "Sheqer stik 5 g, kuti 1000 copë", "Box", 1400, 2, 2),
		("Acesorë Pijesh", "Qumësht kafeje në kupa 10 g, kuti 120 copë", "Box", 1250, 2, 2),
	],
	"Agro Freskia sh.p.k.": [
		("Fruta & Perime", "Domate serre Divjake, kg", "Kg", 100, 20, 1),
		("Fruta & Perime", "Patate Korçe, thes 25 kg", "Unit", 1400, 2, 1),
		("Fruta & Perime", "Qepë e verdhë, thes 10 kg", "Unit", 750, 2, 1),
		("Fruta & Perime", "Kastravec serre, kg", "Kg", 80, 10, 1),
		("Fruta & Perime", "Speca të gjelbër, kg", "Kg", 130, 10, 1),
		("Fruta & Perime", "Sallatë jeshile (marule), copë", "Nos", 65, 20, 1),
		("Fruta & Perime", "Portokall Konispoli, kg (dhjetor-mars)", "Kg", 70, 20, 1),
		("Fruta & Perime", "Mollë Korçe, kg", "Kg", 90, 20, 1),
		("Fruta & Perime", "Banane, kg", "Kg", 150, 10, 1),
		("Fruta & Perime", "Limon, kg", "Kg", 150, 5, 1),
		("Fruta & Perime", "Shalqi Lushnje, kg (qershor-gusht)", "Kg", 35, 50, 1),
		("Mish & Shpendë", "Mish viçi i grirë, kg", "Kg", 1150, 5, 2),
		("Mish & Shpendë", "Fileto viçi, kg", "Kg", 2600, 3, 2),
		("Mish & Shpendë", "Mish qengji me kocka, kg", "Kg", 1150, 5, 2),
		("Mish & Shpendë", "Gjoks pule fileto, kg", "Kg", 600, 5, 2),
		("Mish & Shpendë", "Pulë e plotë, kg", "Kg", 280, 10, 2),
		("Mish & Shpendë", "Suxhuk viçi, kg", "Kg", 1350, 3, 2),
		("Bulmet & Vezë", "Qumësht lope 3.5% 1 L, pako 12", "Pack", 1650, 3, 1),
		("Bulmet & Vezë", "Djathë i bardhë lope në shëllirë, kg", "Kg", 750, 5, 2),
		("Bulmet & Vezë", "Kaçkavall, kg", "Kg", 950, 3, 2),
		("Bulmet & Vezë", "Kos tradicional 1 kg", "Unit", 200, 10, 1),
		("Bulmet & Vezë", "Vezë M, kofshë 30 copë", "Unit", 600, 5, 1),
		("Bulmet & Vezë", "Gjalpë 82% 250 g", "Pack", 360, 10, 2),
		("Bulmet & Vezë", "Ajkë gatimi 35% 1 L", "Unit", 480, 6, 2),
		("Brumëra & Bukë", "Bukë fshati 1 kg", "Nos", 150, 10, 1),
		("Brumëra & Bukë", "Kroasan i ngrirë me gjalpë 60 g, kuti 50 copë", "Box", 2400, 2, 2),
		("Brumëra & Bukë", "Brumë pice i ngrirë 250 g, kuti 40 copë", "Box", 2600, 2, 2),
		("Ushqime të Thata & Salca", "Vaj ulliri ekstra i virgjër shqiptar 5 L", "Unit", 3900, 2, 2),
		("Ushqime të Thata & Salca", "Vaj luledielli 5 L", "Unit", 1150, 4, 2),
		("Ushqime të Thata & Salca", "Oriz Baldo 5 kg", "Unit", 1100, 4, 2),
		("Ushqime të Thata & Salca", "Makarona spageti 500 g, pako 20 copë", "Pack", 2300, 2, 2),
		("Ushqime të Thata & Salca", "Miell tip 00, thes 25 kg", "Unit", 1900, 1, 2),
		("Ushqime të Thata & Salca", "Salcë domate (pelati) 2.5 kg", "Unit", 450, 6, 2),
		("Desserts & Ëmbëlsira", "Akullore vanilje 5 L, vaskë", "Unit", 1900, 2, 2),
	],
	"Deti Jon Seafood sh.p.k.": [
		("Peshk & Meze Deti", "Levrek i kultivuar 400-600 g, kg", "Kg", 1050, 5, 1),
		("Peshk & Meze Deti", "Koce e kultivuar 400-600 g, kg", "Kg", 1050, 5, 1),
		("Peshk & Meze Deti", "Levrek i egër, kg (sipas kapjes)", "Kg", 2600, 2, 1),
		("Peshk & Meze Deti", "Midhje Butrinti, kg", "Kg", 300, 10, 1),
		("Peshk & Meze Deti", "Karkaleca të ngrirë 16/20 me kokë, kg", "Kg", 1300, 5, 2),
		("Peshk & Meze Deti", "Kallamar i pastruar i ngrirë, kg", "Kg", 1100, 5, 2),
		("Peshk & Meze Deti", "Oktapod i freskët, kg", "Kg", 1500, 3, 1),
		("Peshk & Meze Deti", "Koran i Ohrit (Pogradec), kg", "Kg", 3500, 2, 3),
	],
	"Bio Malësia sh.p.k.": [
		("Produkte të Egra, Artizanale & Fshati", "Mjaltë mali Tropojë 1 kg", "Unit", 1600, 3, 3),
		("Produkte të Egra, Artizanale & Fshati", "Djathë dhie Gjirokastër, kg", "Kg", 1000, 3, 3),
		("Produkte të Egra, Artizanale & Fshati", "Trumzë mali e tharë 100 g", "Pack", 250, 10, 3),
		("Produkte të Egra, Artizanale & Fshati", "Kërpudha porçini të thata 250 g", "Pack", 1300, 4, 5),
		("Produkte të Egra, Artizanale & Fshati", "Gështenja Tropoje, kg (tetor-dhjetor)", "Kg", 300, 10, 3),
		("Produkte të Egra, Artizanale & Fshati", "Reçel boronice e egër 400 g", "Unit", 450, 12, 3),
		(
			"Produkte të Egra, Artizanale & Fshati",
			"Pulë fshati e rritur në liri, copë (~2 kg)",
			"Nos",
			1400,
			5,
			3,
		),
	],
	"Gourmet Import Albania sh.p.k.": [
		(
			"Produkte Premium nga e Gjithë Bota",
			"Tartuf i zi i freskët (Tuber aestivum), 100 g",
			"Unit",
			3500,
			1,
			5,
		),
		("Produkte Premium nga e Gjithë Bota", "Parmigiano Reggiano DOP 24 muaj, kg", "Kg", 2600, 2, 3),
		("Produkte Premium nga e Gjithë Bota", "Prosciutto di Parma DOP pa kocka, kg", "Kg", 2900, 2, 3),
		("Produkte Premium nga e Gjithë Bota", "Havjar bli (Acipenser baerii) 50 g", "Unit", 6500, 1, 7),
		("Produkte Premium nga e Gjithë Bota", "Salmon norvegjez i tymosur, kg", "Kg", 3100, 2, 3),
		("Produkte Premium nga e Gjithë Bota", "Shafran fije 1 g", "Unit", 900, 5, 5),
	],
	"HoReCa Pajisje sh.p.k.": [
		("Furra & Skara", "Furrë kombi Unox CHEFTOP 7 x GN 1/1, elektrike", "Unit", 640000, 1, 21),
		("Furra & Skara", "Skarë me gurë llave me gaz, 80 cm", "Unit", 115000, 1, 10),
		("Furra & Skara", "Friteuzë elektrike 2 x 8 L", "Unit", 45000, 1, 7),
		("Furra & Skara", "Furrë pice me dru, 6 pica, ndërtim në vend", "Unit", None, 1, 30),
		("Frigoriferë & Prodhues Akulli", "Frigorifer vertikal inox GN 2/1, 600 L", "Unit", 145000, 1, 10),
		("Frigoriferë & Prodhues Akulli", "Makinë akulli Brema CB 425, 45 kg/24h", "Unit", 175000, 1, 10),
		("Frigoriferë & Prodhues Akulli", "Dhomë frigoriferike sipas projektit", "Unit", None, 1, 30),
		("Sous-Vide & Vakum", "Makinë vakumi me dhomë, shirit 42 cm", "Unit", 270000, 1, 14),
		("Larëse Industriale", "Pjatalarëse me kapuç 50 x 50, 60 cikle/orë", "Unit", 310000, 1, 14),
		("Larëse Industriale", "Gotalarëse nën banak 40 x 40", "Unit", 105000, 1, 10),
		("Tenxhere, Tigaie & Tava GN", "Tenxhere inox 20 L me kapak", "Unit", 6800, 2, 5),
		("Tenxhere, Tigaie & Tava GN", "Tavë GN 1/1 inox, thellësi 65 mm", "Unit", 1750, 6, 5),
		("Tenxhere, Tigaie & Tava GN", "Tigan alumini me veshje 28 cm, induksion", "Unit", 3400, 4, 5),
		("Thika & Vegla Prerëse", "Set thikash Victorinox Fibrox, 6 copë", "Set", 11500, 1, 5),
		("Thika & Vegla Prerëse", "Dërrasë prerëse HACCP 60 x 40 cm (6 ngjyra)", "Set", 13500, 1, 5),
		("Chafing Dishes & Bufete", "Chafing dish GN 1/1 inox me xhel", "Unit", 7800, 4, 7),
		("Chafing Dishes & Bufete", "Bain-marie elektrik 3 x GN 1/3", "Unit", 28000, 1, 10),
		("Termusë & Dispensers", "Dispenser lëngu 2 x 5 L me ftohje", "Unit", 6500, 2, 7),
		("Termusë & Dispensers", "Termos me pompë 3 L", "Unit", 3600, 4, 5),
		("Karroca Industriale", "Karrocë shërbimi inox 3 kate", "Unit", 14500, 2, 7),
		("Karroca Industriale", "Karrocë bagazhesh hoteli, e artë", "Unit", 42000, 1, 14),
		("Porcelan & Pjata", "Pjatë e sheshtë RAK Banquet 27 cm, kuti 6", "Box", 3900, 10, 5),
		("Porcelan & Pjata", "Tas supe RAK Banquet 400 ml, kuti 6", "Box", 3300, 10, 5),
		("Gota & Shishe", "Gotë vere Arcoroc 35 cl, kuti 6", "Box", 1750, 10, 5),
		("Gota & Shishe", "Gotë uji tumbler 30 cl, kuti 12", "Box", 1450, 10, 5),
		("Gota & Shishe", "Karafë xhami 1 L", "Unit", 650, 12, 5),
		("Servise", "Pirun tavoline inox 18/10, pako 12", "Pack", 1950, 10, 5),
		("Servise", "Thikë tavoline inox 18/10, pako 12", "Pack", 2200, 10, 5),
	],
	"Tekstil Hotel Korça sh.p.k.": [
		(
			"Tekstile Dhome & Fjetje",
			"Çarçaf pambuk percale 200 TC 240 x 290 cm, i bardhë",
			"Unit",
			2300,
			20,
			10,
		),
		("Tekstile Dhome & Fjetje", "Këllëf jastëku pambuk 50 x 80 cm", "Unit", 450, 40, 10),
		("Tekstile Dhome & Fjetje", "Runner dekorativ krevati 50 x 240 cm", "Unit", 1800, 10, 14),
		("Tekstile Banjoje", "Peshqir trupi 70 x 140 cm, 500 g/m²", "Unit", 1250, 30, 10),
		("Tekstile Banjoje", "Peshqir duarsh 50 x 100 cm, 500 g/m²", "Unit", 650, 30, 10),
		("Tekstile Banjoje", "Rrobë banje waffle, me logo të qëndisur", "Unit", 2900, 20, 21),
		("Tekstile Banjoje", "Tapet banje 50 x 80 cm, 700 g/m²", "Unit", 700, 30, 10),
		("Tekstile Restoranti", "Mbulesë tavoline 140 x 140 cm, poliester-pambuk", "Unit", 1300, 20, 10),
		("Tekstile Restoranti", "Pecetë pëlhure 45 x 45 cm, pako 12", "Pack", 1800, 5, 10),
		("Uniforma Stafi", "Set kamarieri: këmishë + përparëse", "Set", 3500, 10, 14),
		("Uniforma Stafi", "Xhaketë kuzhinieri pambuk", "Unit", 2600, 10, 14),
		("Uniforma Stafi", "Këpucë pune anti-rrëshqitëse S2", "Pair", 4200, 10, 14),
		("Dyshekë & Mbrojtës", "Dyshek hoteli me susta xhepi 160 x 200 cm", "Unit", 42000, 5, 21),
		("Dyshekë & Mbrojtës", "Mbrojtës dysheku i papërshkueshëm 160 x 200 cm", "Unit", 2400, 10, 10),
		("Jastëkë & Jorgane", "Jastëk mikrofibër hoteli 50 x 80 cm", "Unit", 1200, 20, 10),
		("Jastëkë & Jorgane", "Jorgan mikrofibër 4 stinë 200 x 220 cm", "Unit", 6200, 10, 10),
		("Produkte Higjienike", "Shampo hoteli 30 ml, kuti 300 copë", "Box", 7500, 1, 10),
		("Produkte Higjienike", "Sapun hoteli 15 g me letër, kuti 500 copë", "Box", 6000, 1, 10),
		("Produkte Higjienike", "Papuçe njëpërdorimshe, kuti 100 palë", "Box", 4500, 2, 10),
		("Pajisje Elektrike Dhome", "Tharëse flokësh muri 1200 W", "Unit", 5800, 5, 10),
		("Pajisje Elektrike Dhome", "Kasafortë dhome elektronike për laptop", "Unit", 8700, 5, 14),
		("Pajisje Elektrike Dhome", "Minibar me absorbim 30 L, pa zhurmë", "Unit", 22000, 5, 14),
		("Pajisje Elektrike Dhome", "Set mirëseardhjeje: kazan 0.8 L + tabaka", "Set", 2500, 10, 10),
	],
	"Pastërti Pro sh.p.k.": [
		("Kimikate & Detergjente", "Detergjent pjatalarëse industriale 10 L", "Unit", 3200, 2, 3),
		("Kimikate & Detergjente", "Shkëlqyes pjatalarëse 5 L", "Unit", 2000, 2, 3),
		("Kimikate & Detergjente", "Dezinfektues sipërfaqesh 5 L", "Unit", 1800, 2, 3),
		("Kimikate & Detergjente", "Yndyrë-heqës kuzhine 5 L", "Unit", 2000, 2, 3),
		("Kimikate & Detergjente", "Pastrues xhamash 5 L", "Unit", 1100, 2, 3),
		("Produkte Letre", "Letër higjienike jumbo 2 shtresa, pako 6 rula", "Pack", 1500, 5, 3),
		("Produkte Letre", "Peshqirë letre Z-fold, kuti 3000 fletë", "Box", 1900, 5, 3),
		("Produkte Letre", "Letër kuzhine industriale, pako 2 rula", "Pack", 800, 10, 3),
		("Mjete Pastrimi", "Karrocë housekeeping me qese dhe kapak", "Unit", 24000, 1, 7),
		("Mjete Pastrimi", "Leckë mikrofibër 40 x 40 cm, pako 10", "Pack", 1100, 5, 3),
		("Mjete Pastrimi", "Fshesë me korent profesionale 15 L", "Unit", 17500, 1, 7),
		(
			"Lavanteri, Pastrim & Kopshtari",
			"Lavanteri tekstilesh hoteli (larje + hekurosje), kg",
			"Kg",
			150,
			50,
			2,
		),
		("Lavanteri, Pastrim & Kopshtari", "Pastrim fasade dhe xhamash në lartësi", "Unit", None, 1, 7),
		("Lavanteri, Pastrim & Kopshtari", "Mirëmbajtje kopshti, muaj", "Month", 35000, 1, 7),
	],
	"Mobilieri Adriatik sh.p.k.": [
		("Mobilje Dhome & Akomodimi", "Shtrat dopio 160 x 200 me kokë të veshur", "Unit", 45000, 2, 30),
		("Mobilje Dhome & Akomodimi", "Komodinë dhome me sirtar", "Unit", 9500, 4, 30),
		("Mobilje Dhome & Akomodimi", "Gardërobë 2 dyer me pasqyrë", "Unit", 38000, 2, 30),
		("Mobilje Dhome & Akomodimi", "Shtrat shtesë i palosshëm me dyshek", "Unit", 14000, 2, 14),
		("Divane & Ndenjëse", "Divan lobby 3 vendesh, stof", "Unit", 85000, 1, 30),
		("Divane & Ndenjëse", "Kolltuk lobby", "Unit", 32000, 2, 30),
		("Mobilje Restoranti & Bari", "Karrige restoranti dru ahu", "Unit", 7500, 10, 21),
		("Mobilje Restoranti & Bari", "Tavolinë restoranti 80 x 80 cm", "Unit", 15000, 4, 21),
		("Mobilje Restoranti & Bari", "Stol bari i lartë metal/dru", "Unit", 9000, 6, 21),
		("Mobilje Restoranti & Bari", "Shezlong plazhi alumini me tekstilen", "Unit", 12000, 10, 14),
		("Mobilje Restoranti & Bari", "Mobilim i plotë restoranti sipas projektit", "Unit", None, 1, 45),
	],
	"Smart HoReCa Tech sh.p.k.": [
		("Pikë Shitjeje (POS)", 'Terminal POS Android touchscreen 15.6"', "Unit", 44000, 1, 7),
		("Pikë Shitjeje (POS)", "Printer termik faturash Epson TM-T20III", "Unit", 15500, 1, 5),
		("Pikë Shitjeje (POS)", "Sirtar parash metalik", "Unit", 4900, 1, 5),
		("Pajisje Akomodimi", "Karta RFID për dhoma, kuti 100 copë", "Box", 7800, 1, 7),
		("Pajisje Akomodimi", "Bravë elektronike RFID për derë dhome", "Unit", 13500, 10, 14),
		("Pajisje Akomodimi", "Lexues pasaporte dhe ID për recepsion", "Unit", 25000, 1, 7),
		("Rrjeti & Siguria", "Access point Wi-Fi 6 Ubiquiti U6+", "Unit", 12500, 4, 7),
		("Rrjeti & Siguria", "Kamerë sigurie IP Hikvision 4 MP", "Unit", 6800, 4, 7),
		("Sisteme Menaxhimi", "PMS hoteli në cloud, abonim mujor (deri 50 dhoma)", "Month", 9700, 12, 7),
		(
			"Sisteme Menaxhimi",
			"Channel Manager (Booking, Expedia, Airbnb), abonim mujor",
			"Month",
			4900,
			12,
			7,
		),
		(
			"Sisteme Menaxhimi",
			"Softuer POS restoranti me fiskalizim, abonim mujor për terminal",
			"Month",
			3500,
			12,
			5,
		),
		("Module Integrimi", "Integrim me fiskalizimin elektronik (e-faturë)", "Unit", None, 1, 14),
		("Module Integrimi", "Integrim PMS - POS - kontabilitet", "Unit", None, 1, 21),
	],
	"Mikpritja Consulting sh.p.k.": [
		(
			"Projektim Arkitektural & Interior Design",
			"Projekt interieri për hotel (koncept + 3D)",
			"Unit",
			None,
			1,
			30,
		),
		(
			"Projektim Teknologjik Kuzhine-Bari",
			"Projektim teknologjik kuzhine sipas HACCP",
			"Unit",
			None,
			1,
			21,
		),
		("Projektim & Realizim", "Projektim dhe ndërtim pishine / SPA", "Unit", None, 1, 90),
		("Mystery Shopper & Auditim Shërbimi", "Vizitë mystery shopper me raport", "Unit", 20000, 1, 14),
		("Çertifikime Standardesh", "Përgatitje për certifikim HACCP", "Unit", None, 1, 30),
		("Çertifikime Standardesh", "Përgatitje për ISO 22000", "Unit", None, 1, 60),
		("Shërbime Sigurie", "Roje sigurie 24/7, muaj", "Month", None, 1, 7),
		("Punime & Mirëmbajtje Elektrike", "Elektricist industrial, orë", "Hour", 1800, 2, 2),
		(
			"Konsulencë Operacionale HoReCa",
			"Inxhinieri menuje dhe kontroll i food cost, ditë",
			"Day",
			30000,
			1,
			7,
		),
		("Menaxhim Operacional", "Menaxhim operacional i hotelit, muaj", "Month", None, 1, 30),
		("Trajnim Stafi", "Trajnim barista 2 ditë (deri 8 persona)", "Unit", 40000, 1, 14),
		("Trajnim Stafi", "Trajnim recepsioni dhe shërbimi ndaj klientit, ditë", "Day", 30000, 1, 14),
		("Shërbime Marketingu", "Menaxhim rrjetesh sociale, muaj", "Month", 60000, 3, 7),
		("Shërbime Marketingu", "Fotografi profesionale hoteli, ditë", "Day", 45000, 1, 10),
		("Shërbime Marketingu", "Video promocionale me dron", "Unit", None, 1, 14),
	],
	"Eventi Shqip sh.p.k.": [
		("Rezervo Artistin", "Grup iso-polifonik labërisht për event", "Unit", None, 1, 14),
		("Rezervo Artistin", "DJ për mbrëmje (4 orë)", "Unit", 35000, 1, 7),
		("Rezervo Artistin", "Grup muzike live për dasma", "Unit", None, 1, 30),
		("Organizim Eventesh & Floristë", "Dekorim me lule për dasma", "Unit", None, 1, 14),
		("Organizim Eventesh & Floristë", "Organizim eventi korporativ", "Unit", None, 1, 21),
		("Qira Pajisjesh", "Qira sistemi zëri për event, ditë", "Day", 20000, 1, 3),
		("Qira Pajisjesh", "Qira projektori + ekran, ditë", "Day", 15000, 1, 3),
	],
}

# Other distributors' offers of products already in LISTINGS: distributor: [(title, price, minimum qty, lead days)]
COMPETING_OFFERS = {
	"Bevera Jug sh.p.k.": [
		("Birra Tirana 0.33 L shishe kthyese, arkë 24 copë", 1820, 5, 2),
		("Birra Korça 0.5 L kanoçe, pako 24 copë", 2350, 5, 2),
		("Ujë Tepelena 0.5 L, pako 12 copë", 350, 20, 1),
		("Ujë Tepelena 1.5 L, pako 6 copë", 280, 20, 1),
		("Coca-Cola 0.33 L kanoçe, pako 24 copë", 1780, 5, 2),
		("Red Bull 0.25 L kanoçe, pako 24 copë", 3800, 2, 3),
		("Raki rrushi Skrapar 40% 0.7 L", 680, 6, 2),
		("Konjak Skënderbeu 40% 0.7 L", 740, 6, 2),
		("Whisky Johnnie Walker Red Label 0.7 L", 1590, 6, 3),
		("Verë e bardhë Shesh i Bardhë 0.75 L", 470, 6, 2),
		("Prosecco DOC Extra Dry 0.75 L", 920, 6, 3),
		("Kafe espresso kokërr Lavazza Super Crema 1 kg", 2650, 4, 3),
		("Sheqer stik 5 g, kuti 1000 copë", 1450, 2, 2),
	],
	"Cash & Carry Tirana sh.p.k.": [
		("Birra Tirana 0.33 L shishe kthyese, arkë 24 copë", 1880, 3, 1),
		("Coca-Cola 0.33 L kanoçe, pako 24 copë", 1850, 2, 1),
		("Ujë Tepelena 1.5 L, pako 6 copë", 265, 10, 1),
		("Kafe turke e bluar 500 g", 620, 5, 1),
		("Vaj luledielli 5 L", 1120, 2, 1),
		("Oriz Baldo 5 kg", 1150, 2, 1),
		("Makarona spageti 500 g, pako 20 copë", 2250, 1, 1),
		("Miell tip 00, thes 25 kg", 1950, 1, 1),
		("Salcë domate (pelati) 2.5 kg", 430, 6, 1),
		("Sheqer stik 5 g, kuti 1000 copë", 1380, 1, 1),
		("Letër higjienike jumbo 2 shtresa, pako 6 rula", 1450, 5, 1),
		("Peshqirë letre Z-fold, kuti 3000 fletë", 1950, 3, 1),
		("Detergjent pjatalarëse industriale 10 L", 3350, 1, 1),
	],
	"Tregu Fresk Tirana sh.p.k.": [
		("Domate serre Divjake, kg", 110, 10, 1),
		("Patate Korçe, thes 25 kg", 1350, 2, 1),
		("Qepë e verdhë, thes 10 kg", 720, 2, 1),
		("Kastravec serre, kg", 85, 10, 1),
		("Sallatë jeshile (marule), copë", 60, 20, 1),
		("Mollë Korçe, kg", 95, 20, 1),
		("Banane, kg", 145, 10, 1),
		("Limon, kg", 140, 5, 1),
		("Gjoks pule fileto, kg", 620, 5, 1),
		("Pulë e plotë, kg", 290, 10, 1),
		("Qumësht lope 3.5% 1 L, pako 12", 1620, 3, 1),
		("Djathë i bardhë lope në shëllirë, kg", 780, 5, 1),
		("Kos tradicional 1 kg", 210, 10, 1),
		("Vezë M, kofshë 30 copë", 590, 5, 1),
	],
	"Peshku i Durrësit sh.p.k.": [
		("Levrek i kultivuar 400-600 g, kg", 1100, 5, 1),
		("Koce e kultivuar 400-600 g, kg", 1080, 5, 1),
		("Midhje Butrinti, kg", 320, 10, 1),
		("Karkaleca të ngrirë 16/20 me kokë, kg", 1350, 5, 1),
		("Kallamar i pastruar i ngrirë, kg", 1150, 5, 1),
	],
	"Gastro Equipment Albania sh.p.k.": [
		("Friteuzë elektrike 2 x 8 L", 47000, 1, 5),
		("Makinë akulli Brema CB 425, 45 kg/24h", 169000, 1, 14),
		("Tenxhere inox 20 L me kapak", 7000, 2, 3),
		("Tavë GN 1/1 inox, thellësi 65 mm", 1700, 6, 3),
		("Set thikash Victorinox Fibrox, 6 copë", 11900, 1, 3),
		("Chafing dish GN 1/1 inox me xhel", 7500, 4, 5),
		("Pjatë e sheshtë RAK Banquet 27 cm, kuti 6", 4050, 10, 7),
		("Gotë vere Arcoroc 35 cl, kuti 6", 1700, 10, 5),
		("Gotë uji tumbler 30 cl, kuti 12", 1500, 10, 5),
		("Pirun tavoline inox 18/10, pako 12", 1900, 10, 5),
		("Thikë tavoline inox 18/10, pako 12", 2250, 10, 5),
	],
	"Linen Hotel Durrës sh.p.k.": [
		("Çarçaf pambuk percale 200 TC 240 x 290 cm, i bardhë", 2250, 30, 7),
		("Peshqir trupi 70 x 140 cm, 500 g/m²", 1300, 30, 7),
		("Peshqir duarsh 50 x 100 cm, 500 g/m²", 620, 30, 7),
		("Rrobë banje waffle, me logo të qëndisur", 3100, 20, 14),
		("Tapet banje 50 x 80 cm, 700 g/m²", 690, 30, 7),
		("Jastëk mikrofibër hoteli 50 x 80 cm", 1150, 20, 7),
		("Shampo hoteli 30 ml, kuti 300 copë", 7800, 1, 7),
		("Papuçe njëpërdorimshe, kuti 100 palë", 4300, 2, 7),
	],
	"Fiskal Tech sh.p.k.": [
		('Terminal POS Android touchscreen 15.6"', 46000, 1, 5),
		("Printer termik faturash Epson TM-T20III", 15200, 1, 3),
		("Sirtar parash metalik", 5100, 1, 3),
		("Softuer POS restoranti me fiskalizim, abonim mujor për terminal", 3200, 12, 3),
		("Integrim me fiskalizimin elektronik (e-faturë)", None, 1, 7),
	],
}


def get_listings():
	"""LISTINGS plus COMPETING_OFFERS, as distributor: [(item group, title, uom, price, minimum qty, lead days)]."""
	products = {row[1]: row for rows in LISTINGS.values() for row in rows}
	listings = {d: list(rows) for d, rows in LISTINGS.items()}
	for distributor, offers in COMPETING_OFFERS.items():
		for title, price, minimum_qty, lead_time_days in offers:
			item_group, _title, uom, *_ = products[title]
			listings.setdefault(distributor, []).append(
				(item_group, title, uom, price, minimum_qty, lead_time_days)
			)
	return listings


# Seasonal or currently unavailable
OUT_OF_STOCK = {
	"Shalqi Lushnje, kg (qershor-gusht)",
	"Portokall Konispoli, kg (dhjetor-mars)",
	"Koran i Ohrit (Pogradec), kg",
}

# (distributor, hotel, discount %, commission %)
PARTNERSHIPS = [
	("Pije Shqiptare Distribution sh.p.k.", "Grand Hotel Bulevardi", 8, 3),
	("Agro Freskia sh.p.k.", "Resort Gjiri i Lalzit", 5, 2),
	("HoReCa Pajisje sh.p.k.", "Dhërmi Bay Resort", 10, 4),
	("Tekstil Hotel Korça sh.p.k.", "Hotel Pogradeci Liqen", 7, 3),
]

# (distributor, hotel, overall, quality, delivery, communication, comment) — ratings are 0..1
RATINGS = [
	("Pije Shqiptare Distribution sh.p.k.", "Grand Hotel Bulevardi", 1.0, 1.0, 0.8, 1.0, "Dorëzim i saktë."),
	("Pije Shqiptare Distribution sh.p.k.", "Hotel Plazhi i Durrësit", 0.8, 0.8, 0.8, 0.6, ""),
	("Agro Freskia sh.p.k.", "Resort Gjiri i Lalzit", 0.8, 1.0, 0.6, 0.8, "Produkte të freskëta."),
	("Deti Jon Seafood sh.p.k.", "Dhërmi Bay Resort", 1.0, 1.0, 1.0, 0.8, "Peshk i kapur në mëngjes."),
	("HoReCa Pajisje sh.p.k.", "Dhërmi Bay Resort", 0.6, 0.8, 0.4, 0.6, "Vonesë në instalim."),
	("Tekstil Hotel Korça sh.p.k.", "Hotel Pogradeci Liqen", 0.8, 0.8, 0.8, 1.0, ""),
	("Bio Malësia sh.p.k.", "Hotel Liqeni Shkodër", 1.0, 1.0, 0.8, 0.8, "Mjaltë shumë i mirë."),
	("Bevera Jug sh.p.k.", "Hotel Riviera Vlorë", 0.8, 0.8, 1.0, 0.8, "Furnizim i shpejtë në Vlorë."),
	("Cash & Carry Tirana sh.p.k.", "Hotel Skanderbeg Square Inn", 0.6, 0.8, 0.6, 0.4, ""),
	(
		"Tregu Fresk Tirana sh.p.k.",
		"Grand Hotel Bulevardi",
		0.8,
		0.8,
		1.0,
		0.8,
		"Perime të freskëta çdo mëngjes.",
	),
	("Peshku i Durrësit sh.p.k.", "Hotel Plazhi i Durrësit", 1.0, 1.0, 0.8, 1.0, ""),
	("Gastro Equipment Albania sh.p.k.", "Resort Gjiri i Lalzit", 0.8, 0.8, 0.8, 0.8, ""),
	(
		"Linen Hotel Durrës sh.p.k.",
		"Hotel Plazhi i Durrësit",
		0.6,
		0.6,
		0.8,
		0.8,
		"Peshqirët u zbardhën shpejt.",
	),
]

# Logins to try the marketplace as each actor
USERS = [
	("demo.hotel@example.com", "Demo", "Hotel", "Hotel", "Customer", "Grand Hotel Bulevardi"),
	(
		"demo.distributor@example.com",
		"Demo",
		"Distributor",
		"Distributor",
		"Supplier",
		"Pije Shqiptare Distribution sh.p.k.",
	),
	("demo.hotel2@example.com", "Demo", "Hotel 2", "Hotel", "Customer", "Hotel Riviera Vlorë"),
]


def create_demo():
	for uom in EXTRA_UOMS:
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
	for name, spec in DISTRIBUTORS.items():
		create_distributor(name, *spec)
	for name, spec in HOTELS.items():
		create_hotel(name, *spec)
	listings = get_listings()
	for distributor, rows in listings.items():
		for row in rows:
			create_listing(distributor, *row)
	remove_stale_listings(listings)
	for spec in PARTNERSHIPS:
		create_partnership(*spec)
	for spec in RATINGS:
		create_rating(*spec)
	for spec in USERS:
		create_user(*spec)
	frappe.db.commit()
	print(
		f"HAT demo: {len(DISTRIBUTORS)} distributors, {len(HOTELS)} hotels, "
		f"{frappe.db.count('Item', {'name': ('like', DEMO_ITEM_PREFIX + '%')})} products, "
		f"{sum(len(v) for v in listings.values())} listings, {len(PARTNERSHIPS)} partnerships. "
		f"Logins: {', '.join(u[0] for u in USERS)} / {DEMO_PASSWORD}"
	)


def create_distributor(name, city, categories, coverage, minimum_order):
	if frappe.db.exists("Supplier", name):
		return
	frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": name,
			"supplier_group": "Distributor",
			"supplier_type": "Company",
			"country": "Albania",
			"hat_categories": [{"item_group": c} for c in categories],
			"hat_coverage": [{"territory": t} for t in coverage or []],
			"hat_minimum_order": minimum_order,
			"hat_verified": 1,
			"supplier_details": f"Demo distributor, {city}",
		}
	).insert(ignore_permissions=True)


def create_hotel(name, county, city, stars, hotel_type, rooms, latitude, longitude):
	if frappe.db.exists("Customer", name):
		return
	frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_group": "Hotel",
			"customer_type": "Company",
			"territory": county,
			"hat_city": city,
			"hat_star_rating": stars,
			"hat_hotel_type": hotel_type,
			"hat_number_of_rooms": rooms,
			"hat_latitude": latitude,
			"hat_longitude": longitude,
		}
	).insert(ignore_permissions=True)


def create_listing(distributor, item_group, title, uom, price, minimum_qty, lead_time_days):
	"""Create the listing, or bring an existing one in line with the demo data."""
	name = frappe.db.exists("HAT Listing", {"distributor": distributor, "title": title})
	doc = frappe.get_doc("HAT Listing", name) if name else frappe.new_doc("HAT Listing")
	doc.update(
		{
			"item": ensure_item(title, item_group, uom, distributor),
			"title": title,
			"distributor": distributor,
			"price_type": "Price on Request" if price is None else "Fixed Price",
			"price": price or 0,
			"minimum_qty": minimum_qty,
			"lead_time_days": lead_time_days,
			"availability": "Out of Stock" if title in OUT_OF_STOCK else "Available",
			"published": 1,
			"description": LISTING_NOTE,
		}
	)
	doc.image = frappe.db.get_value("Item", doc.item, "image")
	doc.save(ignore_permissions=True)


def ensure_item(item_name, item_group, uom, distributor):
	"""The catalogue product (ERPNext Item) shared by every distributor that sells it."""
	code = frappe.db.get_value("Item", {"item_name": item_name})
	image = product_icon(item_name, item_group)
	if not code:
		return (
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": next_item_code(item_group),
					"item_name": item_name[:140],
					"description": item_name,
					"item_group": item_group,
					"stock_uom": uom,
					"is_stock_item": 0,
					"is_purchase_item": 1,
					"is_sales_item": 1,
					"include_item_in_manufacturing": 0,
					"supplier_items": [{"supplier": distributor}],
					"image": image,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	item = frappe.get_doc("Item", code)
	# a photo someone uploaded wins over the generated icon
	if not item.image or item.image.startswith(f"/files/{ICON_FILE_PREFIX}"):
		item.db_set("image", image)
	if item.item_group != item_group or distributor not in [s.supplier for s in item.supplier_items]:
		item.item_group = item_group
		if distributor not in [s.supplier for s in item.supplier_items]:
			item.append("supplier_items", {"supplier": distributor})
		item.save(ignore_permissions=True)
	return code


def product_icon(item_name, item_group):
	"""URL of the icon for a product, creating the public file the first time it is needed."""
	name = item_name.lower()
	icon = next((icon for word, icon in NAME_ICONS if word in name), GROUP_ICONS.get(item_group, "package"))
	code = top_category_code(item_group)
	file_name = f"{ICON_FILE_PREFIX}{code.lower()}-{icon}.svg"
	url = f"/files/{file_name}"
	if not frappe.db.exists("File", {"file_url": url}):
		frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": icon_svg(icon, code), "is_private": 0}
		).insert(ignore_permissions=True)
	return url


def top_category_code(item_group):
	for category, subcategories in CATALOGUE.items():
		if item_group == category or item_group in subcategories:
			return CATEGORY_CODES[category]
		if any(item_group in groups for groups in subcategories.values()):
			return CATEGORY_CODES[category]
	return "FB"


def icon_svg(icon, code):
	start, end, colour = ICON_COLOURS[code]
	return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="{start}"/><stop offset="1" stop-color="{end}"/></linearGradient></defs>
<rect width="256" height="256" rx="48" fill="url(#bg)"/>
<circle cx="206" cy="46" r="78" fill="#FFFFFF" opacity="0.22"/>
<g transform="translate(56 56) scale(6)" fill="none" stroke="{colour}" stroke-width="1.5"
stroke-linecap="round" stroke-linejoin="round">{lucide_paths(icon)}</g>
</svg>"""


@cache
def lucide_icons():
	path = frappe.get_app_path("frappe", "public", "icons", "lucide", "icons.svg")
	with open(path) as f:
		return dict(re.findall(r'<symbol[^>]*id="icon-([a-z0-9-]+)"[^>]*>(.*?)</symbol>', f.read(), re.S))


def lucide_paths(icon):
	return " ".join(lucide_icons().get(icon, lucide_icons()["package"]).split())


def remove_stale_listings(listings):
	"""Listings of demo distributors that are no longer in the demo data: delete, or unpublish if ordered."""
	current = {(d, row[1]) for d, rows in listings.items() for row in rows}
	for listing in frappe.get_all(
		"HAT Listing",
		filters={"distributor": ("in", list(DISTRIBUTORS))},
		fields=["name", "distributor", "title"],
	):
		if (listing.distributor, listing.title) in current:
			continue
		if frappe.db.exists("HAT Order Request Item", {"listing": listing.name}):
			frappe.db.set_value("HAT Listing", listing.name, "published", 0)
		else:
			frappe.delete_doc("HAT Listing", listing.name, ignore_permissions=True)


def create_partnership(distributor, hotel, discount, commission):
	if frappe.db.exists("HAT Partnership", {"distributor": distributor, "hotel": hotel}):
		return
	doc = frappe.get_doc(
		{
			"doctype": "HAT Partnership",
			"distributor": distributor,
			"hotel": hotel,
			"start_date": add_days(today(), -90),
			"end_date": add_days(today(), 275),
			"discount_percentage": discount,
			"commission_type": "Percentage",
			"commission_rate": commission,
			"terms": "Partneritet demo: pagesë brenda 30 ditëve nga fatura.",
		}
	).insert(ignore_permissions=True)
	# Demo partnerships start active instead of going through the approval workflow
	frappe.db.set_value("HAT Partnership", doc.name, "status", "Active")


def create_rating(distributor, hotel, rating, quality, delivery, communication, comment):
	if frappe.db.exists("HAT Distributor Rating", {"distributor": distributor, "hotel": hotel}):
		return
	frappe.get_doc(
		{
			"doctype": "HAT Distributor Rating",
			"distributor": distributor,
			"hotel": hotel,
			"rating": rating,
			"quality": quality,
			"delivery": delivery,
			"communication": communication,
			"comment": comment,
		}
	).insert(ignore_permissions=True)


def create_user(email, first_name, last_name, role, allow, for_value):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"send_welcome_email": 0,
				"new_password": DEMO_PASSWORD,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("User Permission", {"user": email, "allow": allow, "for_value": for_value}):
		frappe.get_doc(
			{"doctype": "User Permission", "user": email, "allow": allow, "for_value": for_value}
		).insert(ignore_permissions=True)


def delete_demo():
	"""Remove everything create_demo made, including order requests between demo parties."""
	distributors = [d for d in DISTRIBUTORS if frappe.db.exists("Supplier", d)]
	hotels = [h for h in HOTELS if frappe.db.exists("Customer", h)]
	items = frappe.get_all(
		"HAT Listing", filters={"distributor": ("in", distributors or [""])}, pluck="item", distinct=True
	)
	for doctype, field, values in (
		("HAT Distributor Rating", "distributor", distributors),
		("HAT Distributor Rating", "hotel", hotels),
		("HAT Order Request", "distributor", distributors),
		("HAT Order Request", "hotel", hotels),
		("HAT Partnership", "distributor", distributors),
		("HAT Listing", "distributor", distributors),
	):
		for name in frappe.get_all(doctype, filters={field: ("in", values or [""])}, pluck="name"):
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
	for item in items:
		# keep products that non-demo distributors also sell
		if item and item.startswith(DEMO_ITEM_PREFIX) and not frappe.db.exists("HAT Listing", {"item": item}):
			frappe.delete_doc("Item", item, ignore_permissions=True, force=True)
	for name in frappe.get_all("File", filters={"file_name": ("like", f"{ICON_FILE_PREFIX}%")}, pluck="name"):
		frappe.delete_doc("File", name, ignore_permissions=True, force=True)
	for email, *_ in USERS:
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, ignore_permissions=True, force=True)
	for name in distributors:
		frappe.delete_doc("Supplier", name, ignore_permissions=True, force=True)
	for name in hotels:
		frappe.delete_doc("Customer", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	print(f"HAT demo removed: {len(distributors)} distributors, {len(hotels)} hotels")

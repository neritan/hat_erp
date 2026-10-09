"""HAT product & service tree, loaded into ERPNext as Item Groups.

Source: docs/product_categories.md (from "Pema e produkteve ERP.doc"). Names stay in Albanian.
Each category maps to its subcategories; a subcategory maps to its groups, or to an empty list
when the source lists items directly under it.
"""

CATALOGUE = {
	"Ushqim & Pije": {
		"Pije me Alkool & Të Ftohta": [
			"Pije me Alkool të Lartë",
			"Vera & Shampanjë",
			"Birra",
			"Pije Jo-Alkoolike",
		],
		"Kafe, Çaj & Baza e Barit": ["Kafe", "Çajra", "Shurupë & Pure", "Acesorë Pijesh"],
		"Ushqime të Freskëta & Të Ngrira": [
			"Mish & Shpendë",
			"Peshk & Meze Deti",
			"Brumëra & Bukë",
			"Fruta & Perime",
		],
		"Bulmet & Ushqime të Thata": [
			"Bulmet & Vezë",
			"Ushqime të Thata & Salca",
			"Desserts & Ëmbëlsira",
		],
		"Produkte të Egra, Artizanale & Fshati": [],
		"Produkte Premium nga e Gjithë Bota": [],
	},
	"Pajisje Kuzhine, Enë & Shërbim Restoranti": {
		"Pajisje Industriale Gatimi & Ftohjeje": [
			"Furra & Skara",
			"Frigoriferë & Prodhues Akulli",
			"Sous-Vide & Vakum",
			"Larëse Industriale",
		],
		"Enë Kuzhine & Aksesorë Gatimi": ["Tenxhere, Tigaie & Tava GN", "Thika & Vegla Prerëse"],
		"Pajisje Shërbimi & Karroca": [
			"Chafing Dishes & Bufete",
			"Termusë & Dispensers",
			"Karroca Industriale",
		],
		"Pjata, Gota & Servise": ["Porcelan & Pjata", "Gota & Shishe", "Servise"],
	},
	"Mobilje, Tekstile & Akomodim": {
		"Tekstile Stafi, Restoranti & Dhome": [
			"Uniforma Stafi",
			"Tekstile Dhome & Fjetje",
			"Tekstile Banjoje",
			"Tekstile Restoranti",
		],
		"Dyshekë, Jastëkë & Fjetje": ["Dyshekë & Mbrojtës", "Jastëkë & Jorgane"],
		"Mobilje Hotele, Restorante & Bare": [
			"Mobilje Dhome & Akomodimi",
			"Divane & Ndenjëse",
			"Mobilje Restoranti & Bari",
		],
		"Amenitete & Pajisje Dhome": ["Produkte Higjienike", "Pajisje Elektrike Dhome"],
		"Materiale Pastrimi & Konsumueshëm": ["Kimikate & Detergjente", "Produkte Letre", "Mjete Pastrimi"],
	},
	"Teknologji, Harduer & Softuer ERP-POS": {
		"Harduer": ["Pikë Shitjeje (POS)", "Pajisje Akomodimi", "Rrjeti & Siguria"],
		"Softuer": ["Sisteme Menaxhimi", "Module Integrimi"],
	},
	"Shërbime Profesionale, Projektim & Konsulencë": {
		"Arkitekturë, Projektim & Dizajn": [
			"Projektim Arkitektural & Interior Design",
			"Projektim Teknologjik Kuzhine-Bari",
			"Projektim & Realizim",
		],
		"Auditues, Mystery Shopper & Çertifikime": [
			"Mystery Shopper & Auditim Shërbimi",
			"Çertifikime Standardesh",
		],
		"Siguri Fizike-Teknike & Punime Elektrike": [
			"Shërbime Sigurie",
			"Punime & Mirëmbajtje Elektrike",
		],
		"Konsulencë & Trajnime": [
			"Konsulencë Operacionale HoReCa",
			"Menaxhim Operacional",
			"Trajnim Stafi",
		],
		"Lavanteri, Pastrim & Kopshtari": [],
		"Shërbime Marketingu": [],
		"Evente & Artistë": ["Rezervo Artistin", "Organizim Eventesh & Floristë", "Qira Pajisjesh"],
	},
}

# Short codes for product (Item) codes, e.g. HAT-FB-0001
CATEGORY_CODES = {
	"Ushqim & Pije": "FB",
	"Pajisje Kuzhine, Enë & Shërbim Restoranti": "KT",
	"Mobilje, Tekstile & Akomodim": "RM",
	"Teknologji, Harduer & Softuer ERP-POS": "TC",
	"Shërbime Profesionale, Projektim & Konsulencë": "SV",
}

# Albania's twelve counties (qarqe), used as delivery coverage areas and hotel regions.
COUNTIES = [
	"Berat",
	"Dibër",
	"Durrës",
	"Elbasan",
	"Fier",
	"Gjirokastër",
	"Korçë",
	"Kukës",
	"Lezhë",
	"Shkodër",
	"Tiranë",
	"Vlorë",
]

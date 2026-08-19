// EXACT 200 LANGUAGES DIRECTLY SOURCED FROM OPENALEX API (https://api.openalex.org/works?group_by=language)
export interface LanguageItem {
  id: string;
  label: string;
  flag: string;
  countries: string;
  papersCount?: number;
}

export const ALL_WORLD_LANGUAGES: LanguageItem[] = [
  {
    "id": "all",
    "label": "All Languages",
    "flag": "🌐",
    "countries": "Global Worldwide All Countries",
    "papersCount": 299095609
  },
  {
    "id": "en",
    "label": "English",
    "flag": "🇬🇧",
    "countries": "United States, United Kingdom, Canada, Australia, New Zealand, Ireland, Singapore en English",
    "papersCount": 220952608
  },
  {
    "id": "ja",
    "label": "Japanese (日本語)",
    "flag": "🇯🇵",
    "countries": "Japan ja Japanese",
    "papersCount": 12729581
  },
  {
    "id": "de",
    "label": "German (Deutsch)",
    "flag": "🇩🇪",
    "countries": "Germany, Austria, Switzerland, Luxembourg, Liechtenstein de German",
    "papersCount": 11080411
  },
  {
    "id": "es",
    "label": "Spanish (Español)",
    "flag": "🇪🇸",
    "countries": "Spain, Mexico, Colombia, Argentina, Peru, Chile, Venezuela, Ecuador es Spanish",
    "papersCount": 10423289
  },
  {
    "id": "fr",
    "label": "French (Français)",
    "flag": "🇫🇷",
    "countries": "France, Canada, Belgium, Switzerland, Senegal, Ivory Coast, Cameroon fr French",
    "papersCount": 9164536
  },
  {
    "id": "pt",
    "label": "Portuguese (Português)",
    "flag": "🇵🇹",
    "countries": "Portugal, Brazil, Mozambique, Angola, Guinea-Bissau, Timor-Leste pt Portuguese",
    "papersCount": 5487561
  },
  {
    "id": "zh",
    "label": "Chinese (中文 / 汉语)",
    "flag": "🇨🇳",
    "countries": "China, Taiwan, Hong Kong, Singapore zh Chinese",
    "papersCount": 5057774
  },
  {
    "id": "ru",
    "label": "Russian (Русский)",
    "flag": "🇷🇺",
    "countries": "Russia, Kazakhstan, Belarus, Kyrgyzstan ru Russian",
    "papersCount": 3331656
  },
  {
    "id": "ko",
    "label": "Korean (한국어)",
    "flag": "🇰🇷",
    "countries": "South Korea, North Korea ko Korean",
    "papersCount": 3240610
  },
  {
    "id": "id",
    "label": "Indonesian (Bahasa Indonesia)",
    "flag": "🇮🇩",
    "countries": "Indonesia id Indonesian",
    "papersCount": 3214109
  },
  {
    "id": "it",
    "label": "Italian (Italiano)",
    "flag": "🇮🇹",
    "countries": "Italy, Switzerland, San Marino, Vatican City it Italian",
    "papersCount": 1902013
  },
  {
    "id": "pl",
    "label": "Polish (Polski)",
    "flag": "🇵🇱",
    "countries": "Poland pl Polish",
    "papersCount": 1590640
  },
  {
    "id": "tr",
    "label": "Turkish (Türkçe)",
    "flag": "🇹🇷",
    "countries": "Turkey, Northern Cyprus tr Turkish",
    "papersCount": 1241083
  },
  {
    "id": "nl",
    "label": "Dutch (Nederlands)",
    "flag": "🇳🇱",
    "countries": "Netherlands, Belgium, Suriname nl Dutch",
    "papersCount": 1165408
  },
  {
    "id": "uk",
    "label": "Ukrainian",
    "flag": "🇺🇦",
    "countries": "Ukraine uk Ukrainian",
    "papersCount": 1009338
  },
  {
    "id": "cs",
    "label": "Czech",
    "flag": "🇨🇿",
    "countries": "Czech Republic cs Czech",
    "papersCount": 843484
  },
  {
    "id": "ar",
    "label": "Arabic (العربية)",
    "flag": "🇸🇦",
    "countries": "Saudi Arabia, Egypt, UAE, Iraq, Algeria, Morocco, Jordan, Qatar ar Arabic",
    "papersCount": 820502
  },
  {
    "id": "sv",
    "label": "Swedish",
    "flag": "🇸🇪",
    "countries": "Sweden, Finland sv Swedish",
    "papersCount": 687932
  },
  {
    "id": "fa",
    "label": "Persian (فارسی)",
    "flag": "🇮🇷",
    "countries": "Iran, Afghanistan, Tajikistan fa Persian",
    "papersCount": 525496
  },
  {
    "id": "ca",
    "label": "Catalan",
    "flag": "🇪🇸",
    "countries": "Spain (Catalonia, Valencia), Andorra ca Catalan",
    "papersCount": 468004
  },
  {
    "id": "hr",
    "label": "Croatian",
    "flag": "🇭🇷",
    "countries": "Croatia, Bosnia and Herzegovina hr Croatian",
    "papersCount": 431075
  },
  {
    "id": "fi",
    "label": "Finnish",
    "flag": "🇫🇮",
    "countries": "Finland fi Finnish",
    "papersCount": 346499
  },
  {
    "id": "da",
    "label": "Danish",
    "flag": "🇩🇰",
    "countries": "Denmark, Greenland, Faroe Islands da Danish",
    "papersCount": 335452
  },
  {
    "id": "hu",
    "label": "Hungarian",
    "flag": "🇭🇺",
    "countries": "Hungary hu Hungarian",
    "papersCount": 289469
  },
  {
    "id": "lv",
    "label": "Latvian",
    "flag": "🇱🇻",
    "countries": "Latvia lv Latvian",
    "papersCount": 260176
  },
  {
    "id": "no",
    "label": "Norwegian",
    "flag": "🇳🇴",
    "countries": "Norway no Norwegian",
    "papersCount": 252111
  },
  {
    "id": "el",
    "label": "Modern Greek",
    "flag": "🇬🇷",
    "countries": "Greece, Cyprus el Modern Greek (1453-)",
    "papersCount": 239896
  },
  {
    "id": "lt",
    "label": "Lithuanian",
    "flag": "🇱🇹",
    "countries": "Lithuania lt Lithuanian",
    "papersCount": 177435
  },
  {
    "id": "ms",
    "label": "Malay (Bahasa Melayu)",
    "flag": "🇲🇾",
    "countries": "Malaysia, Brunei, Singapore, Indonesia ms Malay (macrolanguage)",
    "papersCount": 164519
  },
  {
    "id": "sl",
    "label": "Slovenian",
    "flag": "🇸🇮",
    "countries": "Slovenia sl Slovenian",
    "papersCount": 150330
  },
  {
    "id": "th",
    "label": "Thai (ไทย)",
    "flag": "🇹🇭",
    "countries": "Thailand th Thai",
    "papersCount": 143743
  },
  {
    "id": "vi",
    "label": "Vietnamese (Tiếng Việt)",
    "flag": "🇻🇳",
    "countries": "Vietnam vi Vietnamese",
    "papersCount": 93990
  },
  {
    "id": "la",
    "label": "Latin",
    "flag": "📜",
    "countries": "Vatican City, Historical, Scholarly la Latin",
    "papersCount": 91656
  },
  {
    "id": "sh",
    "label": "Serbo-Croatian",
    "flag": "🇷🇸",
    "countries": "Serbia, Croatia, Bosnia and Herzegovina, Montenegro sh Serbo-Croatian",
    "papersCount": 91592
  },
  {
    "id": "ro",
    "label": "Romanian",
    "flag": "🇷🇴",
    "countries": "Romania, Moldova ro Romanian",
    "papersCount": 90348
  },
  {
    "id": "sr",
    "label": "Serbian",
    "flag": "🇷🇸",
    "countries": "Serbia sr Serbian",
    "papersCount": 84992
  },
  {
    "id": "uz",
    "label": "Uzbek",
    "flag": "🇺🇿",
    "countries": "Uzbekistan uz Uzbek",
    "papersCount": 70325
  },
  {
    "id": "sk",
    "label": "Slovak",
    "flag": "🇸🇰",
    "countries": "Slovakia sk Slovak",
    "papersCount": 54837
  },
  {
    "id": "ceb",
    "label": "CEB",
    "flag": "🇵🇭",
    "countries": "Philippines (Cebu, Visayas) ceb CEB",
    "papersCount": 52836
  },
  {
    "id": "he",
    "label": "Hebrew",
    "flag": "🇮🇱",
    "countries": "Israel he Hebrew",
    "papersCount": 50294
  },
  {
    "id": "et",
    "label": "Estonian",
    "flag": "🇪🇪",
    "countries": "Estonia et Estonian",
    "papersCount": 47357
  },
  {
    "id": "af",
    "label": "Afrikaans",
    "flag": "🇿🇦",
    "countries": "South Africa, Namibia af Afrikaans",
    "papersCount": 45369
  },
  {
    "id": "gl",
    "label": "Galician",
    "flag": "🇪🇸",
    "countries": "Spain (Galicia) gl Galician",
    "papersCount": 39257
  },
  {
    "id": "eo",
    "label": "Esperanto",
    "flag": "🌍",
    "countries": "Esperanto, International eo Esperanto",
    "papersCount": 37144
  },
  {
    "id": "eu",
    "label": "Basque",
    "flag": "🇪🇸",
    "countries": "Spain (Basque Country), France eu Basque",
    "papersCount": 35940
  },
  {
    "id": "bg",
    "label": "Bulgarian",
    "flag": "🇧🇬",
    "countries": "Bulgaria bg Bulgarian",
    "papersCount": 30786
  },
  {
    "id": "hi",
    "label": "Hindi (हिन्दी)",
    "flag": "🇮🇳",
    "countries": "India hi Hindi",
    "papersCount": 29060
  },
  {
    "id": "ka",
    "label": "Georgian",
    "flag": "🇬🇪",
    "countries": "Georgia ka Georgian",
    "papersCount": 20875
  },
  {
    "id": "ng",
    "label": "Ndonga",
    "flag": "🌐",
    "countries": "Code ng ng Ndonga",
    "papersCount": 20533
  },
  {
    "id": "war",
    "label": "WAR",
    "flag": "🇵🇭",
    "countries": "Philippines (Waray) war WAR",
    "papersCount": 20020
  },
  {
    "id": "zh-cn",
    "label": "Chinese (中文 / 汉语)",
    "flag": "🌐",
    "countries": "Code zh-cn zh-cn Chinese",
    "papersCount": 16356
  },
  {
    "id": "中文",
    "label": "中文",
    "flag": "🌐",
    "countries": "Code 中文 中文 中文",
    "papersCount": 15815
  },
  {
    "id": "is",
    "label": "Icelandic",
    "flag": "🇮🇸",
    "countries": "Iceland is Icelandic",
    "papersCount": 15685
  },
  {
    "id": "az",
    "label": "Azerbaijani",
    "flag": "🇦🇿",
    "countries": "Azerbaijan az Azerbaijani",
    "papersCount": 13327
  },
  {
    "id": "kk",
    "label": "Kazakh",
    "flag": "🇰🇿",
    "countries": "Kazakhstan kk Kazakh",
    "papersCount": 12585
  },
  {
    "id": "nn",
    "label": "Norwegian Nynorsk",
    "flag": "🌐",
    "countries": "Code nn nn Norwegian Nynorsk",
    "papersCount": 11913
  },
  {
    "id": "mk",
    "label": "Macedonian",
    "flag": "🌐",
    "countries": "Code mk mk Macedonian",
    "papersCount": 10580
  },
  {
    "id": "ga",
    "label": "Irish",
    "flag": "🇮🇪",
    "countries": "Ireland ga Irish",
    "papersCount": 9896
  },
  {
    "id": "sq",
    "label": "Albanian",
    "flag": "🇦🇱",
    "countries": "Albania, Kosovo sq Albanian",
    "papersCount": 9661
  },
  {
    "id": "bs",
    "label": "Bosnian",
    "flag": "🌐",
    "countries": "Code bs bs Bosnian",
    "papersCount": 9158
  },
  {
    "id": "ang",
    "label": "ANG",
    "flag": "📜",
    "countries": "Old English, Historical ang ANG",
    "papersCount": 8921
  },
  {
    "id": "cy",
    "label": "Welsh",
    "flag": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    "countries": "United Kingdom (Wales) cy Welsh",
    "papersCount": 8672
  },
  {
    "id": "ur",
    "label": "Urdu",
    "flag": "🇵🇰",
    "countries": "Pakistan, India ur Urdu",
    "papersCount": 8650
  },
  {
    "id": "bn",
    "label": "Bengali",
    "flag": "🇧🇩",
    "countries": "Bangladesh, India (West Bengal) bn Bengali",
    "papersCount": 7841
  },
  {
    "id": "tl",
    "label": "Tagalog",
    "flag": "🇵🇭",
    "countries": "Philippines tl Tagalog",
    "papersCount": 7625
  },
  {
    "id": "gr",
    "label": "GR",
    "flag": "🌐",
    "countries": "Code gr gr GR",
    "papersCount": 7503
  },
  {
    "id": "ta",
    "label": "Tamil",
    "flag": "🇮🇳",
    "countries": "India (Tamil Nadu), Sri Lanka, Singapore ta Tamil",
    "papersCount": 7190
  },
  {
    "id": "be",
    "label": "Belarusian",
    "flag": "🇧🇾",
    "countries": "Belarus be Belarusian",
    "papersCount": 7016
  },
  {
    "id": "sw",
    "label": "Swahili",
    "flag": "🇰🇪",
    "countries": "Kenya, Tanzania, Uganda, DR Congo sw Swahili (macrolanguage)",
    "papersCount": 6864
  },
  {
    "id": "ua",
    "label": "UA",
    "flag": "🌐",
    "countries": "Code ua ua UA",
    "papersCount": 6838
  },
  {
    "id": "mg",
    "label": "Malagasy",
    "flag": "🇲🇬",
    "countries": "Madagascar mg Malagasy",
    "papersCount": 6423
  },
  {
    "id": "hy",
    "label": "Armenian",
    "flag": "🇦🇲",
    "countries": "Armenia hy Armenian",
    "papersCount": 6346
  },
  {
    "id": "yi",
    "label": "Yiddish",
    "flag": "✡️",
    "countries": "Yiddish, Jewish diaspora yi Yiddish",
    "papersCount": 6173
  },
  {
    "id": "oc",
    "label": "Occitan",
    "flag": "🌐",
    "countries": "Code oc oc Occitan (post 1500)",
    "papersCount": 5830
  },
  {
    "id": "mr",
    "label": "Marathi",
    "flag": "🇮🇳",
    "countries": "India (Maharashtra) mr Marathi",
    "papersCount": 5803
  },
  {
    "id": "cmn",
    "label": "CMN",
    "flag": "🌐",
    "countries": "Code cmn cmn CMN",
    "papersCount": 5196
  },
  {
    "id": "EN",
    "label": "English",
    "flag": "🌐",
    "countries": "Code EN EN English",
    "papersCount": 4833
  },
  {
    "id": "kn",
    "label": "Kannada",
    "flag": "🇮🇳",
    "countries": "India (Karnataka) kn Kannada",
    "papersCount": 4652
  },
  {
    "id": "mn",
    "label": "Mongolian",
    "flag": "🇲🇳",
    "countries": "Mongolia mn Mongolian",
    "papersCount": 4376
  },
  {
    "id": "tg",
    "label": "Tajik",
    "flag": "🇹🇯",
    "countries": "Tajikistan tg Tajik",
    "papersCount": 4295
  },
  {
    "id": "ps",
    "label": "Pushto",
    "flag": "🇦🇫",
    "countries": "Afghanistan, Pakistan ps Pushto",
    "papersCount": 3908
  },
  {
    "id": "und",
    "label": "UND",
    "flag": "🌐",
    "countries": "Code und und UND",
    "papersCount": 3804
  },
  {
    "id": "ne",
    "label": "Nepali",
    "flag": "🇳🇵",
    "countries": "Nepal, India ne Nepali (macrolanguage)",
    "papersCount": 3664
  },
  {
    "id": "enc",
    "label": "ENC",
    "flag": "🌐",
    "countries": "Code enc enc ENC",
    "papersCount": 3657
  },
  {
    "id": "arz",
    "label": "ARZ",
    "flag": "🌐",
    "countries": "Code arz arz ARZ",
    "papersCount": 3626
  },
  {
    "id": "sa",
    "label": "Sanskrit",
    "flag": "📜",
    "countries": "Sanskrit, India, Ancient sa Sanskrit",
    "papersCount": 3306
  },
  {
    "id": "br",
    "label": "Breton",
    "flag": "🌐",
    "countries": "Code br br Breton",
    "papersCount": 3285
  },
  {
    "id": "nds",
    "label": "NDS",
    "flag": "🌐",
    "countries": "Code nds nds NDS",
    "papersCount": 3186
  },
  {
    "id": "jbo",
    "label": "JBO",
    "flag": "🌐",
    "countries": "Code jbo jbo JBO",
    "papersCount": 3095
  },
  {
    "id": "fy",
    "label": "Western Frisian",
    "flag": "🌐",
    "countries": "Code fy fy Western Frisian",
    "papersCount": 3077
  },
  {
    "id": "io",
    "label": "Ido",
    "flag": "🌐",
    "countries": "Code io io Ido",
    "papersCount": 2609
  },
  {
    "id": "FR",
    "label": "French (Français)",
    "flag": "🌐",
    "countries": "Code FR FR French",
    "papersCount": 2203
  },
  {
    "id": "ku",
    "label": "Kurdish",
    "flag": "🇮🇶",
    "countries": "Iraq, Turkey, Iran, Syria ku Kurdish",
    "papersCount": 2194
  },
  {
    "id": "mt",
    "label": "Maltese",
    "flag": "🇲🇹",
    "countries": "Malta mt Maltese",
    "papersCount": 2177
  },
  {
    "id": "ml",
    "label": "Malayalam",
    "flag": "🇮🇳",
    "countries": "India (Kerala) ml Malayalam",
    "papersCount": 2167
  },
  {
    "id": "ast",
    "label": "AST",
    "flag": "🌐",
    "countries": "Code ast ast AST",
    "papersCount": 2054
  },
  {
    "id": "lb",
    "label": "Luxembourgish",
    "flag": "🇱🇺",
    "countries": "Luxembourg lb Luxembourgish",
    "papersCount": 1944
  },
  {
    "id": "als",
    "label": "ALS",
    "flag": "🌐",
    "countries": "Code als als ALS",
    "papersCount": 1932
  },
  {
    "id": "ckb",
    "label": "CKB",
    "flag": "🌐",
    "countries": "Code ckb ckb CKB",
    "papersCount": 1888
  },
  {
    "id": "jv",
    "label": "Javanese (Basa Jawa)",
    "flag": "🇮🇩",
    "countries": "Indonesia (Java) jv Javanese",
    "papersCount": 1756
  },
  {
    "id": "ia",
    "label": "Interlingua",
    "flag": "🌐",
    "countries": "Code ia ia Interlingua (International Auxiliary Language Association)",
    "papersCount": 1563
  },
  {
    "id": "wuu",
    "label": "WUU",
    "flag": "🇨🇳",
    "countries": "China (Shanghainese, Wu) wuu WUU",
    "papersCount": 1529
  },
  {
    "id": "xx",
    "label": "XX",
    "flag": "🌐",
    "countries": "Code xx xx XX",
    "papersCount": 1459
  },
  {
    "id": "su",
    "label": "Sundanese (Basa Sunda)",
    "flag": "🇮🇩",
    "countries": "Indonesia (West Java, Sunda) su Sundanese",
    "papersCount": 1444
  },
  {
    "id": "gd",
    "label": "Scottish Gaelic",
    "flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "countries": "United Kingdom (Scotland) gd Scottish Gaelic",
    "papersCount": 1421
  },
  {
    "id": "ky",
    "label": "Kirghiz",
    "flag": "🇰🇬",
    "countries": "Kyrgyzstan ky Kirghiz",
    "papersCount": 1419
  },
  {
    "id": "wa",
    "label": "Walloon",
    "flag": "🌐",
    "countries": "Code wa wa Walloon",
    "papersCount": 1326
  },
  {
    "id": "te",
    "label": "Telugu",
    "flag": "🇮🇳",
    "countries": "India (Andhra Pradesh, Telangana) te Telugu",
    "papersCount": 1268
  },
  {
    "id": "bo",
    "label": "Tibetan",
    "flag": "🇨🇳",
    "countries": "China (Tibet), India, Nepal bo Tibetan",
    "papersCount": 1262
  },
  {
    "id": "tt",
    "label": "Tatar",
    "flag": "🌐",
    "countries": "Code tt tt Tatar",
    "papersCount": 1196
  },
  {
    "id": "si",
    "label": "Sinhala",
    "flag": "🇱🇰",
    "countries": "Sri Lanka si Sinhala",
    "papersCount": 1185
  },
  {
    "id": "英语",
    "label": "英语",
    "flag": "🌐",
    "countries": "Code 英语 英语 英语",
    "papersCount": 1104
  },
  {
    "id": "ba",
    "label": "Bashkir",
    "flag": "🌐",
    "countries": "Code ba ba Bashkir",
    "papersCount": 1079
  },
  {
    "id": "ht",
    "label": "Haitian",
    "flag": "🌐",
    "countries": "Code ht ht Haitian",
    "papersCount": 1071
  },
  {
    "id": "am",
    "label": "Amharic",
    "flag": "🇪🇹",
    "countries": "Ethiopia am Amharic",
    "papersCount": 958
  },
  {
    "id": "gu",
    "label": "Gujarati",
    "flag": "🇮🇳",
    "countries": "India (Gujarat) gu Gujarati",
    "papersCount": 920
  },
  {
    "id": "ie",
    "label": "Interlingue",
    "flag": "🌐",
    "countries": "Code ie ie Interlingue",
    "papersCount": 900
  },
  {
    "id": "cng",
    "label": "CNG",
    "flag": "🌐",
    "countries": "Code cng cng CNG",
    "papersCount": 838
  },
  {
    "id": "EN-US",
    "label": "EN-US",
    "flag": "🌐",
    "countries": "Code EN-US EN-US EN-US",
    "papersCount": 826
  },
  {
    "id": "ilo",
    "label": "ILO",
    "flag": "🇵🇭",
    "countries": "Philippines (Ilocano) ilo ILO",
    "papersCount": 825
  },
  {
    "id": "lmo",
    "label": "LMO",
    "flag": "🌐",
    "countries": "Code lmo lmo LMO",
    "papersCount": 756
  },
  {
    "id": "mis",
    "label": "MIS",
    "flag": "🌐",
    "countries": "Code mis mis MIS",
    "papersCount": 745
  },
  {
    "id": "rm",
    "label": "Romansh",
    "flag": "🌐",
    "countries": "Code rm rm Romansh",
    "papersCount": 719
  },
  {
    "id": "lo",
    "label": "Lao",
    "flag": "🇱🇦",
    "countries": "Laos lo Lao",
    "papersCount": 718
  },
  {
    "id": "enm",
    "label": "ENM",
    "flag": "🌐",
    "countries": "Code enm enm ENM",
    "papersCount": 695
  },
  {
    "id": "my",
    "label": "Burmese",
    "flag": "🇲🇲",
    "countries": "Myanmar (Burma) my Burmese",
    "papersCount": 687
  },
  {
    "id": "zxx",
    "label": "ZXX",
    "flag": "🌐",
    "countries": "Code zxx zxx ZXX",
    "papersCount": 686
  },
  {
    "id": "Eng",
    "label": "ENG",
    "flag": "🌐",
    "countries": "Code Eng Eng ENG",
    "papersCount": 674
  },
  {
    "id": "nb",
    "label": "Norwegian Bokmål",
    "flag": "🌐",
    "countries": "Code nb nb Norwegian Bokmål",
    "papersCount": 644
  },
  {
    "id": "dv",
    "label": "Dhivehi",
    "flag": "🇲🇻",
    "countries": "Maldives dv Dhivehi",
    "papersCount": 607
  },
  {
    "id": "or",
    "label": "Oriya",
    "flag": "🇮🇳",
    "countries": "India (Odisha) or Oriya (macrolanguage)",
    "papersCount": 605
  },
  {
    "id": "an",
    "label": "Aragonese",
    "flag": "🌐",
    "countries": "Code an an Aragonese",
    "papersCount": 599
  },
  {
    "id": "arb",
    "label": "ARB",
    "flag": "🌐",
    "countries": "Code arb arb ARB",
    "papersCount": 585
  },
  {
    "id": "jp",
    "label": "JP",
    "flag": "🌐",
    "countries": "Code jp jp JP",
    "papersCount": 582
  },
  {
    "id": "vo",
    "label": "Volapük",
    "flag": "🌐",
    "countries": "Code vo vo Volapük",
    "papersCount": 559
  },
  {
    "id": "so",
    "label": "Somali",
    "flag": "🇸🇴",
    "countries": "Somalia, Djibouti, Ethiopia so Somali",
    "papersCount": 554
  },
  {
    "id": "km",
    "label": "Central Khmer",
    "flag": "🇰🇭",
    "countries": "Cambodia km Central Khmer",
    "papersCount": 516
  },
  {
    "id": "kw",
    "label": "Cornish",
    "flag": "🌐",
    "countries": "Code kw kw Cornish",
    "papersCount": 501
  },
  {
    "id": "min",
    "label": "MIN",
    "flag": "🇮🇩",
    "countries": "Indonesia (West Sumatra) min MIN",
    "papersCount": 492
  },
  {
    "id": "영어",
    "label": "영어",
    "flag": "🌐",
    "countries": "Code 영어 영어 영어",
    "papersCount": 487
  },
  {
    "id": "yac",
    "label": "YAC",
    "flag": "🌐",
    "countries": "Code yac yac YAC",
    "papersCount": 478
  },
  {
    "id": "pms",
    "label": "PMS",
    "flag": "🌐",
    "countries": "Code pms pms PMS",
    "papersCount": 473
  },
  {
    "id": "pa",
    "label": "Panjabi",
    "flag": "🇮🇳",
    "countries": "India (Punjab), Pakistan pa Panjabi",
    "papersCount": 464
  },
  {
    "id": "fil",
    "label": "FIL",
    "flag": "🌐",
    "countries": "Code fil fil FIL",
    "papersCount": 430
  },
  {
    "id": "dba",
    "label": "DBA",
    "flag": "🌐",
    "countries": "Code dba dba DBA",
    "papersCount": 420
  },
  {
    "id": "qu",
    "label": "Quechua",
    "flag": "🇵🇪",
    "countries": "Peru, Bolivia, Ecuador qu Quechua",
    "papersCount": 420
  },
  {
    "id": "ENG",
    "label": "ENG",
    "flag": "🌐",
    "countries": "Code ENG ENG ENG",
    "papersCount": 418
  },
  {
    "id": "cu",
    "label": "Church Slavic",
    "flag": "🌐",
    "countries": "Code cu cu Church Slavic",
    "papersCount": 416
  },
  {
    "id": "cpi",
    "label": "CPI",
    "flag": "🌐",
    "countries": "Code cpi cpi CPI",
    "papersCount": 414
  },
  {
    "id": "azb",
    "label": "AZB",
    "flag": "🌐",
    "countries": "Code azb azb AZB",
    "papersCount": 410
  },
  {
    "id": "sco",
    "label": "SCO",
    "flag": "🌐",
    "countries": "Code sco sco SCO",
    "papersCount": 406
  },
  {
    "id": "mul",
    "label": "MUL",
    "flag": "🌐",
    "countries": "Code mul mul MUL",
    "papersCount": 393
  },
  {
    "id": "bqh",
    "label": "BQH",
    "flag": "🌐",
    "countries": "Code bqh bqh BQH",
    "papersCount": 376
  },
  {
    "id": "pnb",
    "label": "PNB",
    "flag": "🌐",
    "countries": "Code pnb pnb PNB",
    "papersCount": 340
  },
  {
    "id": "yue",
    "label": "YUE",
    "flag": "🇭🇰",
    "countries": "Hong Kong, Macau, China (Cantonese) yue YUE",
    "papersCount": 327
  },
  {
    "id": "ory",
    "label": "ORY",
    "flag": "🌐",
    "countries": "Code ory ory ORY",
    "papersCount": 307
  },
  {
    "id": "ug",
    "label": "Uighur",
    "flag": "🌐",
    "countries": "Code ug ug Uighur",
    "papersCount": 303
  },
  {
    "id": "AR",
    "label": "Arabic (العربية)",
    "flag": "🌐",
    "countries": "Code AR AR Arabic",
    "papersCount": 294
  },
  {
    "id": "eng",
    "label": "ENG",
    "flag": "🌐",
    "countries": "Code eng eng ENG",
    "papersCount": 291
  },
  {
    "id": "aig",
    "label": "AIG",
    "flag": "🌐",
    "countries": "Code aig aig AIG",
    "papersCount": 259
  },
  {
    "id": "mi",
    "label": "Maori",
    "flag": "🇳🇿",
    "countries": "New Zealand mi Maori",
    "papersCount": 257
  },
  {
    "id": "eml",
    "label": "EML",
    "flag": "🌐",
    "countries": "Code eml eml EML",
    "papersCount": 231
  },
  {
    "id": "fo",
    "label": "Faroese",
    "flag": "🇫🇴",
    "countries": "Faroe Islands, Denmark fo Faroese",
    "papersCount": 224
  },
  {
    "id": "li",
    "label": "Limburgan",
    "flag": "🌐",
    "countries": "Code li li Limburgan",
    "papersCount": 221
  },
  {
    "id": "gn",
    "label": "Guarani",
    "flag": "🇵🇾",
    "countries": "Paraguay, Argentina gn Guarani",
    "papersCount": 218
  },
  {
    "id": "yo",
    "label": "Yoruba",
    "flag": "🇳🇬",
    "countries": "Nigeria yo Yoruba",
    "papersCount": 215
  },
  {
    "id": "sd",
    "label": "Sindhi",
    "flag": "🇵🇰",
    "countries": "Pakistan, India sd Sindhi",
    "papersCount": 211
  },
  {
    "id": "bar",
    "label": "BAR",
    "flag": "🌐",
    "countries": "Code bar bar BAR",
    "papersCount": 206
  },
  {
    "id": "ce",
    "label": "Chechen",
    "flag": "🌐",
    "countries": "Code ce ce Chechen",
    "papersCount": 203
  },
  {
    "id": "gv",
    "label": "Manx",
    "flag": "🌐",
    "countries": "Code gv gv Manx",
    "papersCount": 202
  },
  {
    "id": "英文",
    "label": "英文",
    "flag": "🌐",
    "countries": "Code 英文 英文 英文",
    "papersCount": 200
  },
  {
    "id": "kaa",
    "label": "KAA",
    "flag": "🌐",
    "countries": "Code kaa kaa KAA",
    "papersCount": 190
  },
  {
    "id": "Fr",
    "label": "French (Français)",
    "flag": "🌐",
    "countries": "Code Fr Fr French",
    "papersCount": 184
  },
  {
    "id": "mwl",
    "label": "MWL",
    "flag": "🌐",
    "countries": "Code mwl mwl MWL",
    "papersCount": 183
  },
  {
    "id": "sah",
    "label": "SAH",
    "flag": "🌐",
    "countries": "Code sah sah SAH",
    "papersCount": 175
  },
  {
    "id": "cn",
    "label": "CN",
    "flag": "🌐",
    "countries": "Code cn cn CN",
    "papersCount": 170
  },
  {
    "id": "cbk",
    "label": "CBK",
    "flag": "🌐",
    "countries": "Code cbk cbk CBK",
    "papersCount": 168
  },
  {
    "id": "cv",
    "label": "Chuvash",
    "flag": "🌐",
    "countries": "Code cv cv Chuvash",
    "papersCount": 162
  },
  {
    "id": "qno",
    "label": "QNO",
    "flag": "🌐",
    "countries": "Code qno qno QNO",
    "papersCount": 158
  },
  {
    "id": "prm",
    "label": "PRM",
    "flag": "🌐",
    "countries": "Code prm prm PRM",
    "papersCount": 151
  },
  {
    "id": "DE",
    "label": "German (Deutsch)",
    "flag": "🌐",
    "countries": "Code DE DE German",
    "papersCount": 150
  },
  {
    "id": "bh",
    "label": "BH",
    "flag": "🌐",
    "countries": "Code bh bh BH",
    "papersCount": 148
  },
  {
    "id": "spa",
    "label": "SPA",
    "flag": "🌐",
    "countries": "Code spa spa SPA",
    "papersCount": 147
  },
  {
    "id": "mzn",
    "label": "MZN",
    "flag": "🌐",
    "countries": "Code mzn mzn MZN",
    "papersCount": 146
  },
  {
    "id": "zh-tw",
    "label": "ZH-TW",
    "flag": "🌐",
    "countries": "Code zh-tw zh-tw ZH-TW",
    "papersCount": 146
  },
  {
    "id": "se",
    "label": "Northern Sami",
    "flag": "🌐",
    "countries": "Code se se Northern Sami",
    "papersCount": 138
  },
  {
    "id": "RUS",
    "label": "RUS",
    "flag": "🌐",
    "countries": "Code RUS RUS RUS",
    "papersCount": 137
  },
  {
    "id": "vec",
    "label": "VEC",
    "flag": "🌐",
    "countries": "Code vec vec VEC",
    "papersCount": 131
  },
  {
    "id": "qxs",
    "label": "QXS",
    "flag": "🌐",
    "countries": "Code qxs qxs QXS",
    "papersCount": 130
  },
  {
    "id": "as",
    "label": "Assamese",
    "flag": "🇮🇳",
    "countries": "India (Assam) as Assamese",
    "papersCount": 129
  },
  {
    "id": "new",
    "label": "NEW",
    "flag": "🌐",
    "countries": "Code new new NEW",
    "papersCount": 123
  },
  {
    "id": "gom",
    "label": "GOM",
    "flag": "🌐",
    "countries": "Code gom gom GOM",
    "papersCount": 117
  },
  {
    "id": "qot",
    "label": "QOT",
    "flag": "🌐",
    "countries": "Code qot qot QOT",
    "papersCount": 116
  },
  {
    "id": "pam",
    "label": "PAM",
    "flag": "🌐",
    "countries": "Code pam pam PAM",
    "papersCount": 115
  },
  {
    "id": "scn",
    "label": "SCN",
    "flag": "🌐",
    "countries": "Code scn scn SCN",
    "papersCount": 112
  },
  {
    "id": "tk",
    "label": "Turkmen",
    "flag": "🇹🇲",
    "countries": "Turkmenistan tk Turkmen",
    "papersCount": 111
  },
  {
    "id": "bi",
    "label": "Bislama",
    "flag": "🌐",
    "countries": "Code bi bi Bislama",
    "papersCount": 110
  },
  {
    "id": "cjy",
    "label": "CJY",
    "flag": "🌐",
    "countries": "Code cjy cjy CJY",
    "papersCount": 109
  },
  {
    "id": "hsb",
    "label": "HSB",
    "flag": "🌐",
    "countries": "Code hsb hsb HSB",
    "papersCount": 109
  },
  {
    "id": "TH",
    "label": "Thai (ไทย)",
    "flag": "🌐",
    "countries": "Code TH TH Thai",
    "papersCount": 107
  }
];

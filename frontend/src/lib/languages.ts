// EXACT 93 LANGUAGES SUPPORTED BY MULTILINGUAL E5 EMBEDDING MODEL (intfloat/multilingual-e5-small)
// Synchronized with OpenAlex research publications database
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
    "countries": "Global Worldwide All Supported Languages",
    "papersCount": 298753714
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
    "id": "mr",
    "label": "Marathi",
    "flag": "🇮🇳",
    "countries": "India (Maharashtra) mr Marathi",
    "papersCount": 5803
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
    "id": "ps",
    "label": "Pushto",
    "flag": "🇦🇫",
    "countries": "Afghanistan, Pakistan ps Pushto",
    "papersCount": 3908
  },
  {
    "id": "ne",
    "label": "Nepali",
    "flag": "🇳🇵",
    "countries": "Nepal, India ne Nepali (macrolanguage)",
    "papersCount": 3664
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
    "id": "fy",
    "label": "Western Frisian",
    "flag": "🌐",
    "countries": "Code fy fy Western Frisian",
    "papersCount": 3077
  },
  {
    "id": "ku",
    "label": "Kurdish",
    "flag": "🇮🇶",
    "countries": "Iraq, Turkey, Iran, Syria ku Kurdish",
    "papersCount": 2194
  },
  {
    "id": "ml",
    "label": "Malayalam",
    "flag": "🇮🇳",
    "countries": "India (Kerala) ml Malayalam",
    "papersCount": 2167
  },
  {
    "id": "jv",
    "label": "Javanese (Basa Jawa)",
    "flag": "🇮🇩",
    "countries": "Indonesia (Java) jv Javanese",
    "papersCount": 1756
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
    "id": "te",
    "label": "Telugu",
    "flag": "🇮🇳",
    "countries": "India (Andhra Pradesh, Telangana) te Telugu",
    "papersCount": 1268
  },
  {
    "id": "si",
    "label": "Sinhala",
    "flag": "🇱🇰",
    "countries": "Sri Lanka si Sinhala",
    "papersCount": 1185
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
    "id": "lo",
    "label": "Lao",
    "flag": "🇱🇦",
    "countries": "Laos lo Lao",
    "papersCount": 718
  },
  {
    "id": "my",
    "label": "Burmese",
    "flag": "🇲🇲",
    "countries": "Myanmar (Burma) my Burmese",
    "papersCount": 687
  },
  {
    "id": "or",
    "label": "Oriya",
    "flag": "🇮🇳",
    "countries": "India (Odisha) or Oriya (macrolanguage)",
    "papersCount": 605
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
    "id": "pa",
    "label": "Panjabi",
    "flag": "🇮🇳",
    "countries": "India (Punjab), Pakistan pa Panjabi",
    "papersCount": 464
  },
  {
    "id": "ug",
    "label": "Uighur",
    "flag": "🌐",
    "countries": "Code ug ug Uighur",
    "papersCount": 303
  },
  {
    "id": "sd",
    "label": "Sindhi",
    "flag": "🇵🇰",
    "countries": "Pakistan, India sd Sindhi",
    "papersCount": 211
  },
  {
    "id": "as",
    "label": "Assamese",
    "flag": "🇮🇳",
    "countries": "India (Assam) as Assamese",
    "papersCount": 129
  },
  {
    "id": "ha",
    "label": "Hausa (Harshen Hausa)",
    "flag": "🇳🇬",
    "countries": "Nigeria, Niger, Ghana ha Hausa",
    "papersCount": 41
  },
  {
    "id": "om",
    "label": "Oromo (Afaan Oromoo)",
    "flag": "🇪🇹",
    "countries": "Ethiopia, Kenya om Oromo",
    "papersCount": 13
  },
  {
    "id": "xh",
    "label": "Xhosa (isiXhosa)",
    "flag": "🇿🇦",
    "countries": "South Africa, Zimbabwe xh Xhosa",
    "papersCount": 8
  }
];

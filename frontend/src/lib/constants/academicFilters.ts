export interface SearchFilterState {
  yearFrom: string;
  yearTo: string;
  minCitations: string;
  languages: string[];
  fieldsOfStudy: string[];
  scopusQuartiles: string[];
  sintaTiers: string[];
  excludePreprints: boolean;
  openAccessOnly: boolean;
}

export const DEFAULT_SEARCH_FILTER: SearchFilterState = {
  yearFrom: "",
  yearTo: "",
  minCitations: "",
  languages: [],
  fieldsOfStudy: [],
  scopusQuartiles: [],
  sintaTiers: [],
  excludePreprints: false,
  openAccessOnly: false,
};

export const OPENALEX_DOMAINS = [
  { id: "Computer Science", label: "Computer Science & AI", icon: "💻" },
  { id: "Engineering", label: "Engineering & Technology", icon: "⚙️" },
  { id: "Medicine", label: "Medicine & Health", icon: "🩺" },
  { id: "Mathematics", label: "Mathematics & Statistics", icon: "📐" },
  { id: "Physics", label: "Physics", icon: "⚛️" },
  { id: "Chemistry", label: "Chemistry", icon: "🧪" },
  { id: "Biology", label: "Biology & Life Sciences", icon: "🧬" },
  { id: "Materials Science", label: "Materials Science", icon: "🔬" },
  { id: "Environmental Science", label: "Environmental Science", icon: "🌿" },
  { id: "Geology", label: "Geology & Earth Sciences", icon: "🌍" },
  { id: "Geography", label: "Geography & GIS", icon: "🗺️" },
  { id: "Economics", label: "Economics & Econometrics", icon: "📈" },
  { id: "Business", label: "Business & Management", icon: "💼" },
  { id: "Psychology", label: "Psychology & Cognitive", icon: "🧠" },
  { id: "Sociology", label: "Sociology & Social Science", icon: "👥" },
  { id: "Political Science", label: "Political Science & Law", icon: "⚖️" },
  { id: "Philosophy", label: "Philosophy & Ethics", icon: "📜" },
  { id: "History", label: "History & Archaeology", icon: "🏛️" },
  { id: "Art", label: "Art & Humanities", icon: "🎨" },
];

export const SCOPUS_QUARTILES = [
  { id: "Q1", label: "Q1", desc: "Top 25%" },
  { id: "Q2", label: "Q2", desc: "Top 50%" },
  { id: "Q3", label: "Q3", desc: "Top 75%" },
  { id: "Q4", label: "Q4", desc: "Bottom 25%" },
];

export const SINTA_TIERS = [
  { id: "S1", label: "SINTA 1" },
  { id: "S2", label: "SINTA 2" },
  { id: "S3", label: "SINTA 3" },
  { id: "S4", label: "SINTA 4" },
  { id: "S5", label: "SINTA 5" },
  { id: "S6", label: "SINTA 6" },
];
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import enTranslations from './locales/en.json';

type LocaleDict = Record<string, string>;

const loadedLocales: Record<string, LocaleDict> = {
  en: enTranslations as LocaleDict,
};

const localeLoaders: Record<string, () => Promise<{ default: LocaleDict }>> = {
  id: () => import('./locales/id.json'),
  es: () => import('./locales/es.json'),
  fr: () => import('./locales/fr.json'),
  de: () => import('./locales/de.json'),
  zh: () => import('./locales/zh.json'),
  'zh-TW': () => import('./locales/zh-TW.json'),
  ja: () => import('./locales/ja.json'),
  ko: () => import('./locales/ko.json'),
  pt: () => import('./locales/pt.json'),
  ru: () => import('./locales/ru.json'),
  it: () => import('./locales/it.json'),
  ar: () => import('./locales/ar.json'),
  nl: () => import('./locales/nl.json'),
  tr: () => import('./locales/tr.json'),
  pl: () => import('./locales/pl.json'),
  vi: () => import('./locales/vi.json'),
  th: () => import('./locales/th.json'),
  hi: () => import('./locales/hi.json'),
  uk: () => import('./locales/uk.json'),
  cs: () => import('./locales/cs.json'),
  sv: () => import('./locales/sv.json'),
  el: () => import('./locales/el.json'),
  da: () => import('./locales/da.json'),
  fi: () => import('./locales/fi.json'),
  no: () => import('./locales/no.json'),
  hu: () => import('./locales/hu.json'),
  ro: () => import('./locales/ro.json'),
  ms: () => import('./locales/ms.json'),
  he: () => import('./locales/he.json'),
  fa: () => import('./locales/fa.json'),
  bn: () => import('./locales/bn.json'),
  tl: () => import('./locales/tl.json'),
  ur: () => import('./locales/ur.json'),
  sk: () => import('./locales/sk.json'),
};

type I18nContextType = {
  language: string;
  setLanguage: (lang: string) => void;
  t: (key: string, variables?: Record<string, string>) => string;
};

let currentActiveLanguage = 'en';

const getStoredLanguage = (): string | null => {
  try {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined' && window.localStorage) {
      return window.localStorage.getItem('system_language');
    }
  } catch {}
  return null;
};

const setStoredLanguage = (lang: string) => {
  try {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined' && window.localStorage) {
      window.localStorage.setItem('system_language', lang);
    }
  } catch {}
};

export function getResolvedLanguage(): string {
  const saved = getStoredLanguage() || 'auto';
  if (saved && saved !== 'auto') return saved;
  if (typeof navigator !== 'undefined' && navigator.language) {
    const browserFullLang = navigator.language;
    const browserLang = browserFullLang.split('-')[0];
    if (localeLoaders[browserFullLang]) return browserFullLang;
    if (localeLoaders[browserLang] || browserLang === 'en') return browserLang;
  }
  return currentActiveLanguage || 'en';
}

export function getSystemTranslation(key: string, variables?: Record<string, string>, fallbackText?: string): string {
  const lang = currentActiveLanguage || getResolvedLanguage();
  const dict = loadedLocales[lang] || loadedLocales['en'];
  let text = dict?.[key] || loadedLocales['en']?.[key] || fallbackText || key;

  if (variables) {
    Object.keys(variables).forEach((vKey) => {
      text = text.replace(new RegExp(`{${vKey}}`, 'g'), variables[vKey]);
    });
  }

  return text;
}

export function registerLoadedLocale(lang: string, dict: LocaleDict) {
  loadedLocales[lang] = dict;
}

export function setGlobalLanguage(lang: string) {
  currentActiveLanguage = lang;
}

if (typeof window !== 'undefined') {
  const initLang = getResolvedLanguage();
  currentActiveLanguage = initLang;
  if (initLang !== 'en' && !loadedLocales[initLang] && localeLoaders[initLang]) {
    localeLoaders[initLang]().then((mod) => {
      loadedLocales[initLang] = mod.default;
    }).catch(() => {});
  }
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState(() => {
    return getStoredLanguage() || 'auto';
  });

  const [activeLanguage, setActiveLanguage] = useState('en');
  const [localeVersion, setLocaleVersion] = useState(0);

  useEffect(() => {
    let resolved = 'en';
    if (language === 'auto') {
      if (typeof navigator !== 'undefined' && navigator.language) {
        const browserFullLang = navigator.language;
        const browserLang = browserFullLang.split('-')[0];
        if (localeLoaders[browserFullLang]) {
          resolved = browserFullLang;
        } else if (localeLoaders[browserLang] || browserLang === 'en') {
          resolved = browserLang;
        }
      }
    } else {
      resolved = language;
    }

    currentActiveLanguage = resolved;
    setActiveLanguage(resolved);

    if (resolved !== 'en' && !loadedLocales[resolved] && localeLoaders[resolved]) {
      localeLoaders[resolved]()
        .then((mod) => {
          loadedLocales[resolved] = mod.default;
          setLocaleVersion((v) => v + 1);
        })
        .catch((err) => {
          console.warn(`[i18n] Failed to load locale ${resolved}:`, err);
        });
    }
  }, [language]);

  const setLanguage = (lang: string) => {
    setLanguageState(lang);
    setStoredLanguage(lang);
    const resolved = lang === 'auto' ? getResolvedLanguage() : lang;
    currentActiveLanguage = resolved;
    if (resolved !== 'en' && !loadedLocales[resolved] && localeLoaders[resolved]) {
      localeLoaders[resolved]().then((mod) => {
        loadedLocales[resolved] = mod.default;
        setLocaleVersion((v) => v + 1);
      }).catch(() => {});
    }
  };

  const t = useCallback((key: string, variables?: Record<string, string>) => {
    if (activeLanguage || localeVersion) {
      // Intentionally reference to recompute on language switch
    }
    return getSystemTranslation(key, variables);
  }, [activeLanguage, localeVersion]);

  return (
    <I18nContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useTranslation() {
  const context = useContext(I18nContext);
  if (context === undefined) {
    throw new Error('useTranslation must be used within an I18nProvider');
  }
  return context;
}

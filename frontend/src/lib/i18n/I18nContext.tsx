import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { languages } from './languages';
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

const I18nContext = createContext<I18nContextType | undefined>(undefined);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('system_language') || 'auto';
    }
    return 'auto';
  });

  const [activeLanguage, setActiveLanguage] = useState('en');
  const [localeVersion, setLocaleVersion] = useState(0);

  useEffect(() => {
    let resolved = 'en';
    if (language === 'auto') {
      if (typeof navigator !== 'undefined') {
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
    if (typeof window !== 'undefined') {
      localStorage.setItem('system_language', lang);
    }
  };

  const t = useCallback((key: string, variables?: Record<string, string>) => {
    const langDict = loadedLocales[activeLanguage] || loadedLocales['en'];
    let text = langDict?.[key] || loadedLocales['en']?.[key] || key;

    if (variables) {
      Object.keys(variables).forEach((vKey) => {
        text = text.replace(new RegExp(`{${vKey}}`, 'g'), variables[vKey]);
      });
    }

    return text;
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

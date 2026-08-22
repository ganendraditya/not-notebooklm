import React, { createContext, useContext, useState, useEffect } from 'react';
import { languages } from './languages';

type TranslationDictionary = {
  [key: string]: { [key: string]: string };
};

// Start with a basic dictionary. Will be expanded.
import { generatedTranslations as translations } from "./generated_translations";

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

  useEffect(() => {
    if (language === 'auto') {
      const browserLang = navigator.language.split('-')[0];
      setActiveLanguage(translations[browserLang] ? browserLang : 'en');
    } else {
      setActiveLanguage(language);
    }
  }, [language]);

  const setLanguage = (lang: string) => {
    setLanguageState(lang);
    if (typeof window !== 'undefined') {
      localStorage.setItem('system_language', lang);
    }
  };

  const t = (key: string, variables?: Record<string, string>) => {
    const langDict = translations[activeLanguage] || translations['en'];
    let text = langDict[key] || translations['en'][key] || key;

    if (variables) {
      Object.keys(variables).forEach((vKey) => {
        text = text.replace(new RegExp(`{${vKey}}`, 'g'), variables[vKey]);
      });
    }

    return text;
  };

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

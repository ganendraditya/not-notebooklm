import { useTheme, type AppearanceMode } from "@/lib/theme";
import { useTranslation, languages } from "@/lib/i18n";

export default function GeneralTab() {
  const { t, language, setLanguage } = useTranslation();
  const { appearance, setAppearance } = useTheme();

  const handleAppearanceChange = (val: string) => {
    setAppearance(val as AppearanceMode);
  };

  return (
    <div>
      <h3 className="text-sm font-semibold text-app-text">{t("settings.general")}</h3>

      <div className="divide-y divide-app-divider mt-4">
        {/* Appearance */}
        <div className="flex items-center justify-between gap-6 py-3">
          <span className="min-w-0 flex-1 text-sm text-app-text truncate">
            {t("settings.appearance")}
          </span>
          <select
            value={appearance}
            onChange={(e) => handleAppearanceChange(e.target.value)}
            className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer"
          >
            <option value="system">{t("settings.appearance.system")}</option>
            <option value="dark">{t("settings.appearance.dark")}</option>
            <option value="light">{t("settings.appearance.light")}</option>
          </select>
        </div>

        {/* Language */}
        <div className="flex items-center justify-between gap-6 py-3">
          <span className="min-w-0 flex-1 text-sm text-app-text truncate">
            {t("settings.language")}
          </span>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="shrink-0 w-44 bg-app-input-surface border border-app-border text-xs text-app-text rounded-lg px-3 py-1.5 outline-none cursor-pointer truncate"
          >
            <option value="auto">{t("language.auto")}</option>
            {languages.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name} ({lang.nativeName})
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

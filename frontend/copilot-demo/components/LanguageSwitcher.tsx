'use client';

import { useLocale, useTranslations } from 'next-intl';
import { usePathname, useRouter } from '../i18n/routing';
import { ChangeEvent, useTransition } from 'react';

export default function LanguageSwitcher() {
    const t = useTranslations('Home.systemStatus'); // Just using some translation or generic
    const locale = useLocale();
    const router = useRouter();
    const pathname = usePathname();
    const [isPending, startTransition] = useTransition();

    const onSelectChange = (e: ChangeEvent<HTMLSelectElement>) => {
        const nextLocale = e.target.value;
        startTransition(() => {
            router.replace(pathname, { locale: nextLocale });
        });
    };

    return (
        <div className="">
            <select
                defaultValue={locale}
                className="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all cursor-pointer"
                onChange={onSelectChange}
                disabled={isPending}
            >
                <option value="en">🇺🇸 English</option>
                <option value="zh">🇨🇳 中文</option>
            </select>
        </div>
    );
}

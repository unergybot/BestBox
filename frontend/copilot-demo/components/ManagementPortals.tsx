"use client";

import { useTranslations } from 'next-intl';
import { ExternalLink, Package, Bot, BarChart3, Search, Database, Activity } from 'lucide-react';

export function ManagementPortals() {
    const t = useTranslations('Home.portals');

    const portals = [
        {
            id: 'erp',
            name: t('erp'),
            url: 'http://localhost:8002',
            icon: <Package size={20} />,
            bg: 'bg-blue-100',
            text: 'text-blue-600',
            hover: 'group-hover:bg-blue-600',
            border: 'hover:border-blue-200',
            desc: 'Manufacturing & CRM'
        },
        {
            id: 'clawdbot',
            name: t('clawdbot'),
            url: 'http://localhost:6001/?token=a2ca49f969529dcdbebad8db8056ed1a15a03d6b7058d178',
            icon: <Bot size={20} />,
            bg: 'bg-purple-100',
            text: 'text-purple-600',
            hover: 'group-hover:bg-purple-600',
            border: 'hover:border-purple-200',
            desc: 'AI Gateway & Admin'
        },
        {
            id: 'grafana',
            name: t('grafana'),
            url: 'http://localhost:3001',
            icon: <BarChart3 size={20} />,
            bg: 'bg-orange-100',
            text: 'text-orange-600',
            hover: 'group-hover:bg-orange-600',
            border: 'hover:border-orange-200',
            desc: 'Observability Dashboards'
        },
        {
            id: 'jaeger',
            name: t('jaeger'),
            url: 'http://localhost:16686',
            icon: <Search size={20} />,
            bg: 'bg-red-100',
            text: 'text-red-600',
            hover: 'group-hover:bg-red-600',
            border: 'hover:border-red-200',
            desc: 'Distributed Tracing'
        },
        {
            id: 'prometheus',
            name: t('prometheus'),
            url: 'http://localhost:9090',
            icon: <Activity size={20} />,
            bg: 'bg-green-100',
            text: 'text-green-600',
            hover: 'group-hover:bg-green-600',
            border: 'hover:border-green-200',
            desc: 'Metrics & Alerts'
        },
        {
            id: 'qdrant',
            name: t('qdrant'),
            url: 'http://localhost:6333/dashboard',
            icon: <Database size={20} />,
            bg: 'bg-indigo-100',
            text: 'text-indigo-600',
            hover: 'group-hover:bg-indigo-600',
            border: 'hover:border-indigo-200',
            desc: 'Vector Database'
        }
    ];

    return (
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
            <h2 className="text-2xl font-semibold mb-4 text-gray-800 flex items-center gap-2">
                <ExternalLink size={24} className="text-blue-600" />
                {t('title')}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {portals.map((portal) => (
                    <a
                        key={portal.id}
                        href={portal.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`group flex items-center p-4 rounded-xl border border-gray-100 ${portal.border} hover:bg-blue-50 transition-all cursor-pointer shadow-sm hover:shadow-md`}
                    >
                        <div className={`p-3 rounded-lg mr-4 ${portal.bg} ${portal.text} ${portal.hover} group-hover:text-white transition-colors`}>
                            {portal.icon}
                        </div>
                        <div className="flex-1">
                            <div className="font-bold text-gray-900 flex items-center justify-between">
                                {portal.name}
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5">
                                {portal.desc}
                            </div>
                        </div>
                    </a>
                ))}
            </div>
        </div>
    );
}

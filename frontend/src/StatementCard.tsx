import { useState } from 'react'
import { Button, Group, Paper, Select, Stack, Switch, Text, TextInput, Title } from '@mantine/core'
import { useT, useToast } from '@hubra/plugin-sdk'
import { downloadStatement, sendStatement } from './api'

type FormValue = string | number | boolean | null

/** Props of the `finance.settings` slot: the finance module's settings and how to save some of them. */
interface Props {
  config: Record<string, unknown>
  save: (values: Record<string, FormValue>) => Promise<void>
  busy: boolean
}

/** Finanzen › Einstellungen › Abrechnung: the monthly account statement. */
export function StatementCard({ config, save, busy }: Props) {
  const { t, i18n } = useT()
  const { notify } = useToast()
  const [enabled, setEnabled] = useState(config.statement_enabled === true)
  const [email, setEmail] = useState(String(config.statement_email ?? ''))
  const [sending, setSending] = useState(false)
  // This month so far, then the twelve before it.
  const months = Array.from({ length: 13 }, (_, i) => {
    const d = new Date()
    d.setDate(1)
    d.setMonth(d.getMonth() - i)
    return {
      value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`,
      label: d.toLocaleString(i18n.language, { month: 'long', year: 'numeric' }),
    }
  })
  const [month, setMonth] = useState(months[1].value)
  const saved = String(config.statement_email ?? '')

  const sendNow = async () => {
    setSending(true)
    try {
      const res = await sendStatement(month)
      notify(
        'success',
        t('finance.statement.sent', 'Kontoauszug unterwegs'),
        t('finance.statement.sentTo', 'An {{email}}', { email: res.to }),
      )
    } catch (err) {
      notify('error', t('common.error', 'Fehler'), (err as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <Paper withBorder p="lg">
      <Title order={3} mb={4}>
        {t('finance.statement.title', 'Monatlicher Kontoauszug')}
      </Title>
      <Text size="sm" c="dimmed" mb="md">
        {t(
          'finance.statement.intro',
          'Am 1. jedes Monats ein PDF mit Saldo, Summen pro Kategorie, allen Buchungen und den offenen Rechnungen des Vormonats, zum Beispiel an die Kassierin oder die Revision.',
        )}
      </Text>
      <Stack gap="md" maw={520}>
        <Switch
          label={t('finance.statement.enabled', 'Jeden Monat per E-Mail senden')}
          checked={enabled}
          onChange={(e) => setEnabled(e.currentTarget.checked)}
        />
        <TextInput
          type="email"
          label={t('finance.statement.email', 'An diese Adresse')}
          placeholder="kasse@verein.ch"
          value={email}
          onChange={(e) => setEmail(e.currentTarget.value)}
          error={
            enabled && !email.includes('@')
              ? t('finance.statement.emailNeeded', 'Eine E-Mail-Adresse ist nötig.')
              : undefined
          }
        />
      </Stack>
      <Group justify="flex-end" mt="md">
        <Button
          loading={busy}
          disabled={enabled && !email.includes('@')}
          onClick={() => save({ statement_enabled: enabled, statement_email: email.trim() })}
        >
          {t('common.save', 'Speichern')}
        </Button>
      </Group>
      <Group mt="lg" gap="sm" align="flex-end" wrap="wrap">
        <Select
          label={t('finance.statement.month', 'Monat')}
          data={months}
          value={month}
          onChange={(v) => v && setMonth(v)}
          allowDeselect={false}
          w={200}
        />
        <Button variant="default" onClick={() => void downloadStatement(month)}>
          {t('finance.statement.download', 'PDF herunterladen')}
        </Button>
        <Button
          variant="default"
          loading={sending}
          disabled={!saved.includes('@')}
          onClick={() => void sendNow()}
        >
          {t('finance.statement.sendNow', 'Jetzt senden')}
        </Button>
      </Group>
    </Paper>
  )
}


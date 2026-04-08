"use client"

import { useState, useCallback } from "react"
import { useMutation } from "@tanstack/react-query"
import { Header } from "@/components/header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import {
  Upload,
  FileText,
  CheckCircle,
  AlertCircle,
  Loader2,
  X,
  Download,
} from "lucide-react"

interface ParsedCompany {
  company_name: string
  email?: string
  phone?: string
  city?: string
  website?: string
}

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [parsedData, setParsedData] = useState<ParsedCompany[]>([])
  const [parseError, setParseError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [importResult, setImportResult] = useState<{
    created: number
    duplicates: number
    errors: number
  } | null>(null)

  const importMutation = useMutation({
    mutationFn: (companies: ParsedCompany[]) =>
      api.importLeads(
        companies.map((c) => ({
          ...c,
          source: "csv_import",
        }))
      ),
    onSuccess: (data) => {
      setImportResult({
        created: data.created,
        duplicates: data.duplicates,
        errors: data.errors,
      })
    },
  })

  const parseCSV = useCallback((text: string) => {
    const lines = text.trim().split("\n")
    if (lines.length < 2) {
      setParseError("CSV должен содержать заголовок и хотя бы одну строку данных")
      return []
    }

    const headerLine = lines[0].toLowerCase()
    const headers = headerLine.split(/[,;]/).map((h) => h.trim().replace(/"/g, ""))

    // Map column names
    const nameIdx = headers.findIndex((h) =>
      ["name", "company", "company_name", "название", "компания"].includes(h)
    )
    const emailIdx = headers.findIndex((h) =>
      ["email", "почта", "e-mail", "mail"].includes(h)
    )
    const phoneIdx = headers.findIndex((h) =>
      ["phone", "телефон", "тел", "mobile"].includes(h)
    )
    const cityIdx = headers.findIndex((h) =>
      ["city", "город", "address", "адрес"].includes(h)
    )
    const websiteIdx = headers.findIndex((h) =>
      ["website", "сайт", "site", "url", "web"].includes(h)
    )

    if (nameIdx === -1) {
      setParseError(
        "Не найдена колонка с названием компании (name, company, company_name, название, компания)"
      )
      return []
    }

    const companies: ParsedCompany[] = []
    const delimiter = headerLine.includes(";") ? ";" : ","

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim()
      if (!line) continue

      // Simple CSV parsing (handles quoted values)
      const values: string[] = []
      let current = ""
      let inQuotes = false

      for (const char of line) {
        if (char === '"') {
          inQuotes = !inQuotes
        } else if (char === delimiter && !inQuotes) {
          values.push(current.trim())
          current = ""
        } else {
          current += char
        }
      }
      values.push(current.trim())

      const companyName = values[nameIdx]?.replace(/"/g, "")
      if (!companyName) continue

      companies.push({
        company_name: companyName,
        email: emailIdx >= 0 ? values[emailIdx]?.replace(/"/g, "") : undefined,
        phone: phoneIdx >= 0 ? values[phoneIdx]?.replace(/"/g, "") : undefined,
        city: cityIdx >= 0 ? values[cityIdx]?.replace(/"/g, "") : undefined,
        website: websiteIdx >= 0 ? values[websiteIdx]?.replace(/"/g, "") : undefined,
      })
    }

    return companies
  }, [])

  const handleFile = useCallback(
    (selectedFile: File) => {
      setFile(selectedFile)
      setParseError(null)
      setImportResult(null)

      const reader = new FileReader()
      reader.onload = (e) => {
        const text = e.target?.result as string
        const companies = parseCSV(text)
        setParsedData(companies)
      }
      reader.onerror = () => {
        setParseError("Ошибка чтения файла")
      }
      reader.readAsText(selectedFile)
    },
    [parseCSV]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)

      const droppedFile = e.dataTransfer.files[0]
      if (droppedFile && droppedFile.name.endsWith(".csv")) {
        handleFile(droppedFile)
      } else {
        setParseError("Пожалуйста, загрузите CSV файл")
      }
    },
    [handleFile]
  )

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0]
      if (selectedFile) {
        handleFile(selectedFile)
      }
    },
    [handleFile]
  )

  const handleImport = () => {
    if (parsedData.length > 0) {
      importMutation.mutate(parsedData)
    }
  }

  const handleReset = () => {
    setFile(null)
    setParsedData([])
    setParseError(null)
    setImportResult(null)
  }

  return (
    <div className="min-h-screen">
      <Header
        title="Импорт компаний"
        description="Загрузите CSV файл с данными компаний"
      />

      <div className="p-6 space-y-6">
        {/* Upload Area */}
        {!file && (
          <Card>
            <CardContent className="pt-6">
              <div
                onDragOver={(e) => {
                  e.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-12 text-center transition-all ${
                  isDragging
                    ? "border-indigo-500 bg-indigo-500/10"
                    : "border-zinc-700 hover:border-zinc-600"
                }`}
              >
                <Upload
                  className={`h-12 w-12 mx-auto mb-4 ${
                    isDragging ? "text-indigo-400" : "text-zinc-500"
                  }`}
                />
                <h3 className="text-lg font-medium text-zinc-200 mb-2">
                  Перетащите CSV файл сюда
                </h3>
                <p className="text-sm text-zinc-500 mb-4">
                  или нажмите для выбора файла
                </p>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileInput}
                  className="hidden"
                  id="file-input"
                />
                <label htmlFor="file-input">
                  <Button asChild variant="outline">
                    <span>Выбрать файл</span>
                  </Button>
                </label>

                <div className="mt-6 p-4 rounded-lg bg-zinc-800/50 text-left">
                  <p className="text-sm font-medium text-zinc-300 mb-2">
                    Формат CSV:
                  </p>
                  <code className="text-xs text-zinc-400 block">
                    name,email,phone,city,website
                    <br />
                    ООО Пример,hr@example.com,+7999123456,Москва,example.com
                  </code>
                </div>
              </div>

              {parseError && (
                <div className="mt-4 flex items-center gap-3 p-4 rounded-lg bg-red-600/20 border border-red-500/30">
                  <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
                  <p className="text-sm text-red-400">{parseError}</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* File Info & Preview */}
        {file && !importResult && (
          <>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-indigo-400" />
                    {file.name}
                  </CardTitle>
                  <Button variant="ghost" size="sm" onClick={handleReset}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <Badge variant="secondary">
                    {parsedData.length} компаний
                  </Badge>
                  <span className="text-sm text-zinc-500">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* Preview Table */}
            {parsedData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Предпросмотр данных</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="rounded-lg border border-zinc-800 overflow-hidden">
                    <div className="max-h-96 overflow-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-12">#</TableHead>
                            <TableHead>Компания</TableHead>
                            <TableHead>Email</TableHead>
                            <TableHead>Телефон</TableHead>
                            <TableHead>Город</TableHead>
                            <TableHead>Сайт</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {parsedData.slice(0, 100).map((company, idx) => (
                            <TableRow key={idx}>
                              <TableCell className="text-zinc-500">
                                {idx + 1}
                              </TableCell>
                              <TableCell className="font-medium">
                                {company.company_name}
                              </TableCell>
                              <TableCell className="text-zinc-400">
                                {company.email || "-"}
                              </TableCell>
                              <TableCell className="text-zinc-400">
                                {company.phone || "-"}
                              </TableCell>
                              <TableCell className="text-zinc-400">
                                {company.city || "-"}
                              </TableCell>
                              <TableCell className="text-zinc-400">
                                {company.website || "-"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                    {parsedData.length > 100 && (
                      <div className="p-3 bg-zinc-800/50 text-center text-sm text-zinc-500">
                        Показано 100 из {parsedData.length} записей
                      </div>
                    )}
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <Button variant="outline" onClick={handleReset}>
                      Отмена
                    </Button>
                    <Button
                      onClick={handleImport}
                      disabled={importMutation.isPending}
                    >
                      {importMutation.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Upload className="mr-2 h-4 w-4" />
                      )}
                      {importMutation.isPending
                        ? "Импортируем..."
                        : `Импортировать ${parsedData.length} компаний`}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}

        {/* Import Result */}
        {importResult && (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-8">
                <div className="flex justify-center mb-6">
                  <div className="h-16 w-16 rounded-full bg-emerald-600/20 flex items-center justify-center">
                    <CheckCircle className="h-8 w-8 text-emerald-400" />
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-zinc-100 mb-6">
                  Импорт завершён
                </h3>

                <div className="grid grid-cols-3 gap-4 max-w-md mx-auto mb-8">
                  <div className="p-4 rounded-lg bg-emerald-600/20 border border-emerald-500/30">
                    <p className="text-2xl font-bold text-emerald-400">
                      {importResult.created}
                    </p>
                    <p className="text-sm text-zinc-400">Создано</p>
                  </div>
                  <div className="p-4 rounded-lg bg-amber-600/20 border border-amber-500/30">
                    <p className="text-2xl font-bold text-amber-400">
                      {importResult.duplicates}
                    </p>
                    <p className="text-sm text-zinc-400">Дубликатов</p>
                  </div>
                  <div className="p-4 rounded-lg bg-red-600/20 border border-red-500/30">
                    <p className="text-2xl font-bold text-red-400">
                      {importResult.errors}
                    </p>
                    <p className="text-sm text-zinc-400">Ошибок</p>
                  </div>
                </div>

                <Button onClick={handleReset}>
                  Загрузить ещё
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Help */}
        <Card className="border-indigo-600/20 bg-indigo-600/5">
          <CardContent className="pt-6">
            <h3 className="font-medium text-indigo-400 mb-2">
              Поддерживаемые колонки
            </h3>
            <ul className="space-y-1 text-sm text-zinc-400">
              <li>
                <strong>name</strong> (обязательно) — название компании
              </li>
              <li>
                <strong>email</strong> — email для связи
              </li>
              <li>
                <strong>phone</strong> — телефон
              </li>
              <li>
                <strong>city</strong> или <strong>address</strong> — город/адрес
              </li>
              <li>
                <strong>website</strong> — сайт компании
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

import { compileFromFile } from 'json-schema-to-typescript'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
const dir = fileURLToPath(new URL('../src/types/', import.meta.url))
await mkdir(dir, { recursive: true })
const schemaDir = fileURLToPath(new URL('../src/schemas/', import.meta.url))
await mkdir(schemaDir, { recursive: true })
const controlTypes = ['ControlStatus', 'CommandReceipt', 'OperatorControl', 'ControlCommand']
for (const name of ['Health', 'AtcsStatus', 'IntersectionConfig', 'TrafficEvent', 'TrafficEvents', 'SessionView', 'TrafficView', ...controlTypes]) {
  const schema = fileURLToPath(new URL(`../../contracts/schemas/${name}.json`, import.meta.url))
  const value = await compileFromFile(schema, {
    bannerComment: `/* Generated from contracts/${controlTypes.includes(name) ? 'control' : name === 'TrafficView' ? 'traffic' : 'models'}.py. Do not edit manually. */`,
    declareExternallyReferenced: true,
  })
  const file = `${dir}/${name}.ts`
  const schemaCopy = `${schemaDir}/${name}.json`
  const rawSchema = await readFile(schema, 'utf8')
  if (process.argv.includes('--check')) {
    if (await readFile(file, 'utf8') !== value) throw new Error(`Kontrak berbeda: ${name}`)
    if (await readFile(schemaCopy, 'utf8') !== rawSchema) throw new Error(`Schema berbeda: ${name}`)
  } else {
    await writeFile(file, value)
    await writeFile(schemaCopy, rawSchema)
  }
}
const geometrySource = fileURLToPath(new URL('../../configs/map-geometry.json', import.meta.url))
const geometryDirectory = fileURLToPath(new URL('../src/geometry/', import.meta.url))
const geometryTarget = `${geometryDirectory}/map-geometry.json`
const geometry = await readFile(geometrySource, 'utf8')
if (process.argv.includes('--check')) {
  if (await readFile(geometryTarget, 'utf8') !== geometry) throw new Error('Geometri peta frontend belum sinkron.')
} else {
  await mkdir(geometryDirectory, { recursive: true })
  await writeFile(geometryTarget, geometry)
}
console.log('Tipe frontend dan geometri peta sinkron dengan sumber proyek.')

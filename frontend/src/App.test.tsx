import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'

describe('LinkerForge interface', () => {
  beforeEach(() => {
    window.location.hash = '#design'
  })

  it('opens as an application workspace and states the scientific limitation', () => {
    render(<App />)
    expect(screen.getByRole('navigation', { name: /workflow navigation/i })).toBeInTheDocument()
    expect(screen.getByText(/computational predictions are not evidence of biological function/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/domain a amino-acid sequence/i)).toBeInTheDocument()
    expect(screen.queryByText(/^overview$/i)).not.toBeInTheDocument()
  })

  it('shows the complete four-stage workflow', () => {
    render(<App />)
    const navigation = screen.getByRole('navigation', { name: /workflow navigation/i })
    expect(within(navigation).getByRole('link', { name: /design input/i })).toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: /candidates/i })).toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: /structure/i })).toBeInTheDocument()
    expect(within(navigation).getByRole('link', { name: /results/i })).toBeInTheDocument()
  })

  it('keeps the labelled preset action on Candidates rather than Design input', () => {
    render(<App />)
    expect(screen.queryByRole('button', { name: /load labelled preset example/i })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: /candidates/i }))
    expect(screen.getByRole('button', { name: /load labelled preset example/i })).toBeInTheDocument()
  })

  it('does not hard-code unrelated individual references as a predicted fusion', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: /structure/i }))
    expect(screen.getByText(/no full-fusion structure loaded/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /individual domain references/i }))
    expect(screen.getByText(/no reference structure loaded/i)).toBeInTheDocument()
    expect(screen.queryByTitle(/sfGFP experimental structure/i)).not.toBeInTheDocument()
    expect(screen.getByText(/does not guess a reference structure/i)).toBeInTheDocument()
  })

  it('accepts two custom domains and offers full-fusion templates without invented coordinates', () => {
    render(<App />)
    expect(screen.getByRole('slider')).toHaveAttribute('min', '5')
    fireEvent.change(screen.getByLabelText(/domain a amino-acid sequence/i), { target: { value: 'ACDEFG' } })
    fireEvent.change(screen.getByLabelText(/domain b amino-acid sequence/i), { target: { value: 'HIKLMN' } })
    fireEvent.click(screen.getByRole('button', { name: /generate candidate set and review/i }))
    expect(screen.getByText(/generated 4 auditable design candidates and required controls/i)).toBeInTheDocument()
    const generated = screen.getByLabelText(/custom fusion candidates/i)
    expect(within(generated).getByText(/full fusion: 27 residues/i)).toBeInTheDocument()
    expect(within(generated).getAllByRole('button')).toHaveLength(4)
    expect(screen.getByText(/why this page comes before structure/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/domain a amino-acid sequence/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /continue with selected candidate/i }))
    expect(screen.getByText(/no full-fusion structure loaded/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /open full screen/i }))
    expect(screen.getByRole('button', { name: /close full screen/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: /continue to results/i }))
    expect(screen.getByText(/required evidence checklist/i)).toBeInTheDocument()
    expect(screen.getByText(/no structure prediction has been started/i)).toBeInTheDocument()
    expect(screen.queryByText(/^experimental validation$/i)).not.toBeInTheDocument()
  })
})

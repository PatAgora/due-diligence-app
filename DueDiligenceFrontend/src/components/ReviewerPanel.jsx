import React, { useState, useEffect } from 'react';
import '../styles/agora-theme.css';
import { useParams, useNavigate } from 'react-router-dom';
import { useModuleSettings } from '../contexts/ModuleSettingsContext';
import { usePermissions } from '../contexts/PermissionsContext';
import { useFieldVisibility } from '../contexts/FieldVisibilityContext';
import './ReviewerPanel.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function ReviewerPanel() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { isModuleEnabled } = useModuleSettings();
  const { canView, canEdit } = usePermissions();
  const { isFieldVisible } = useFieldVisibility();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeSections, setActiveSections] = useState(new Set()); // Track multiple open sections
  const [selectedOutcome, setSelectedOutcome] = useState(''); // Track outcome for conditional fields
  const [saving, setSaving] = useState(false); // Track save state for outreach
  const [outreachDate1, setOutreachDate1] = useState('');
  const [chaser1Date, setChaser1Date] = useState('');
  const [chaser2Date, setChaser2Date] = useState('');
  const [chaser3Date, setChaser3Date] = useState('');
  const [ntcDate, setNtcDate] = useState('');
  
  // Decision section state
  const [decisionData, setDecisionData] = useState({
    outcome: '',
    rationale: '',
    financial_crime_reason: '',
    sme_query: '',
    case_summary: ''
  });
  
  // AI SME Referrals state
  const [aiSmeReferrals, setAiSmeReferrals] = useState([]);
  const [loadingAiReferrals, setLoadingAiReferrals] = useState(false);
  
  // SME Query visibility state (only show if user clicks "Refer for Technical Guidance" or if query already exists)
  const [showSmeQuery, setShowSmeQuery] = useState(false);
  
  // Identity Verification (Sumsub) state
  const [identityVerification, setIdentityVerification] = useState(null);
  const [loadingIdentityVerification, setLoadingIdentityVerification] = useState(false);

  useEffect(() => {
    if (taskId) {
      fetchTaskData();
      fetchAiSmeReferrals();
      fetchIdentityVerification();
    }
  }, [taskId]);

  // PDF Export state
  const [exportingPdf, setExportingPdf] = useState(false);
  const [pdfLibsReady, setPdfLibsReady] = useState(false);

  // Check if PDF libraries are loaded
  useEffect(() => {
    const checkLibs = () => {
      const ready = !!(window.html2canvas && window.jspdf && window.jspdf.jsPDF);
      setPdfLibsReady(ready);
      if (!ready) {
        // Retry after a short delay in case scripts are still loading
        setTimeout(checkLibs, 500);
      }
    };
    checkLibs();
  }, []);

  // PDF Export functionality
  const handleExportPdf = async (e) => {
    e.preventDefault();
    console.log('Export PDF button clicked');
    
    // Check if libraries are loaded
    if (!pdfLibsReady || !window.html2canvas || !window.jspdf || !window.jspdf.jsPDF) {
      alert('PDF libraries are still loading. Please wait a moment and try again.');
      console.error('Missing libraries:', {
        html2canvas: !!window.html2canvas,
        jspdf: !!window.jspdf,
        jsPDF: !!(window.jspdf && window.jspdf.jsPDF),
        pdfLibsReady
      });
      return;
    }

    console.log('Starting PDF export...');
    setExportingPdf(true);

    // Save current active sections state (declare outside try for catch access)
    const originalActiveSections = new Set(activeSections);
    let restoreCollapses = [];

    try {
      // Expand all sections for PDF export (including QC Assessment, SME, Identity Verification, etc.)
      const allSections = new Set(['customer', 'ddg', 'screening', 'outreach', 'decision', 'ai_sme', 'identity_verification', 'sme', 'qc']);
      setActiveSections(allSections);

      // Also expand Bootstrap collapse elements
      const collapses = Array.prototype.slice.call(document.querySelectorAll('.collapse'));
      restoreCollapses = [];
      collapses.forEach((el) => {
        const isShown = el.classList.contains('show');
        restoreCollapses.push({ el, shown: isShown });
        if (!isShown) {
          el.classList.add('show');
          el.style.height = 'auto';
          el.style.display = '';
        }
      });

      // Wait for React to re-render after state update
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Force React to flush updates by accessing DOM
      const forceUpdate = document.querySelector('.case-main');
      if (forceUpdate) {
        forceUpdate.offsetHeight; // Force reflow
      }
      
      // Wait again for any async rendering
      await new Promise(resolve => setTimeout(resolve, 300));

      // Force a reflow to ensure all content is rendered
      document.body.offsetHeight;
      
      // Ensure all card bodies are visible
      const allCardBodies = document.querySelectorAll('.card-body');
      allCardBodies.forEach(body => {
        body.style.display = '';
        body.style.visibility = 'visible';
        body.style.height = 'auto';
        body.style.maxHeight = 'none';
        body.style.overflow = 'visible';
      });

      // Gather the cards in the main column to export
      const container = document.querySelector('.case-main');
      let cards = container ? Array.prototype.slice.call(container.querySelectorAll('.card')) : [];

      // Log for debugging
      console.log('Found cards for PDF export:', cards.length);
      cards.forEach((card, idx) => {
        const cardTitle = card.querySelector('.card-header h5, .card-header h6, .card-title');
        console.log(`Card ${idx}:`, cardTitle ? cardTitle.textContent : 'No title');
      });

      // Fallback if no cards found: export the container
      if (!cards.length && container) cards = [container];

      if (!cards.length) {
        // Restore state before returning
        setActiveSections(originalActiveSections);
        restoreCollapses.forEach((r) => {
          if (!r.shown) {
            r.el.classList.remove('show');
            r.el.style.height = '';
          }
        });
        alert('No content found to export.');
        setExportingPdf(false);
        return;
      }

      // Create PDF doc (A4 portrait)
      const pdf = new window.jspdf.jsPDF({ unit: 'pt', format: 'a4', orientation: 'p' });
      const pageW = pdf.internal.pageSize.getWidth();
      const pageH = pdf.internal.pageSize.getHeight();
      const margin = 24;
      const ts = new Date().toLocaleString();

      // Header
      const addHeader = (pageNum) => {
        pdf.setFontSize(10);
        pdf.setTextColor(120);
        pdf.text('Review Export • ' + ts + (pageNum ? (' • Page ' + pageNum) : ''), margin, margin);
        pdf.setDrawColor(220);
        pdf.line(margin, margin + 6, pageW - margin, margin + 6);
      };

      let first = true;
      let pageNum = 1;
      const headerHeight = margin + 12;
      const availableHeight = pageH - headerHeight - margin;
      let currentY = headerHeight;

      // Helper function to add a new page
      const addNewPage = () => {
        pdf.addPage();
        pageNum++;
        addHeader(pageNum);
        currentY = headerHeight;
      };

      for (let i = 0; i < cards.length; i++) {
        const card = cards[i];
        // Skip if explicitly marked to exclude
        if (card.matches && card.matches('[data-pdf-exclude="1"]')) continue;

        // Scroll card into view to ensure it's rendered
        card.scrollIntoView({ behavior: 'instant', block: 'nearest' });
        
        // Ensure card is visible and expanded before rendering
        card.style.display = '';
        card.style.visibility = 'visible';
        card.style.overflow = 'visible';
        card.style.height = 'auto';
        card.style.maxHeight = 'none';
        card.style.position = 'relative';
        
        const cardBody = card.querySelector('.card-body');
        if (cardBody) {
          // Force card body to be visible
          cardBody.style.display = '';
          cardBody.style.visibility = 'visible';
          cardBody.style.overflow = 'visible';
          cardBody.style.height = 'auto';
          cardBody.style.maxHeight = 'none';
          cardBody.style.opacity = '1';
          
          // Check if card body has content - log for debugging
          const cardTitle = card.querySelector('.card-header h5, .card-header h6, .card-title');
          const cardTitleText = cardTitle ? cardTitle.textContent : 'Unknown';
          const tableRows = cardBody.querySelectorAll('table tbody tr');
          console.log(`Card "${cardTitleText}": ${tableRows.length} table rows found`);
        }
        
        // Ensure tables are fully visible
        const tables = card.querySelectorAll('table');
        tables.forEach(table => {
          table.style.display = '';
          table.style.visibility = 'visible';
          table.style.overflow = 'visible';
          table.style.height = 'auto';
          table.style.maxHeight = 'none';
          
          // Ensure tbody is visible
          const tbody = table.querySelector('tbody');
          if (tbody) {
            tbody.style.display = '';
            tbody.style.visibility = 'visible';
          }
        });
        
        // Force a reflow after style changes
        card.offsetHeight;

        // Calculate actual content height - check all tables and content
        let actualHeight = card.scrollHeight || card.offsetHeight;
        const cardTables = card.querySelectorAll('table');
        if (cardTables.length > 0) {
          // Get the maximum height from all tables
          let maxTableHeight = 0;
          cardTables.forEach(table => {
            const tableHeight = table.scrollHeight || table.offsetHeight;
            const tableRect = table.getBoundingClientRect();
            maxTableHeight = Math.max(maxTableHeight, tableHeight, tableRect.height);
          });
          // Use the larger of card height or table height
          actualHeight = Math.max(actualHeight, maxTableHeight);
        }
        
        // Render entire card to canvas
        let canvas;
        try {
          // Wait a moment for any pending renders
          await new Promise(resolve => setTimeout(resolve, 100));
          
          // Use a more reliable method to get the full height
          // Force layout calculation
          const computedStyle = window.getComputedStyle(card);
          const paddingTop = parseInt(computedStyle.paddingTop) || 0;
          const paddingBottom = parseInt(computedStyle.paddingBottom) || 0;
          
          // Get the actual rendered height including all content
          const cardRect = card.getBoundingClientRect();
          const cardBody = card.querySelector('.card-body');
          let bodyHeight = 0;
          if (cardBody) {
            const bodyRect = cardBody.getBoundingClientRect();
            bodyHeight = bodyRect.height;
            // Check all tables in the body
            const bodyTables = cardBody.querySelectorAll('table');
            bodyTables.forEach(table => {
              const tableRect = table.getBoundingClientRect();
              bodyHeight = Math.max(bodyHeight, tableRect.height, table.scrollHeight);
            });
          }
          
          // Use the maximum of card height, body height, or calculated height
          const finalHeight = Math.max(
            actualHeight,
            cardRect.height,
            bodyHeight + paddingTop + paddingBottom,
            card.scrollHeight
          );
          
          canvas = await window.html2canvas(card, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff',
            windowWidth: document.documentElement.scrollWidth,
            windowHeight: Math.max(document.documentElement.scrollHeight, finalHeight * 2),
            logging: false,
            removeContainer: false,
            allowTaint: true,
            height: finalHeight,
            width: card.scrollWidth || card.offsetWidth,
            onclone: (clonedDoc, clonedWindow) => {
              // Ensure all collapsed sections are expanded in the clone
              const clonedCollapses = clonedDoc.querySelectorAll('.collapse');
              clonedCollapses.forEach((el) => {
                el.classList.add('show');
                el.style.height = 'auto';
                el.style.display = '';
                el.style.overflow = 'visible';
                el.style.maxHeight = 'none';
              });
              
              // Ensure all card bodies are visible
              const clonedCardBodies = clonedDoc.querySelectorAll('.card-body');
              clonedCardBodies.forEach((body) => {
                body.style.display = '';
                body.style.visibility = 'visible';
                body.style.overflow = 'visible';
                body.style.height = 'auto';
                body.style.maxHeight = 'none';
              });
              
              // Ensure all tables are visible and fully rendered
              const clonedTables = clonedDoc.querySelectorAll('table');
              clonedTables.forEach((table) => {
                table.style.display = '';
                table.style.visibility = 'visible';
                table.style.overflow = 'visible';
                table.style.height = 'auto';
                table.style.maxHeight = 'none';
                
                // Ensure tbody is visible
                const tbody = table.querySelector('tbody');
                if (tbody) {
                  tbody.style.display = '';
                  tbody.style.visibility = 'visible';
                  tbody.style.height = 'auto';
                  tbody.style.maxHeight = 'none';
                }
              });
            },
            ignoreElements: (element) => {
              return element.tagName === 'SCRIPT' || element.tagName === 'IFRAME';
            }
          });
          
          // Validate canvas was created and has content
          if (!canvas || canvas.width === 0 || canvas.height === 0) {
            throw new Error('Canvas is empty or invalid');
          }
          
          // Log canvas dimensions for debugging
          const cardTitle = card.querySelector('.card-header h5, .card-header h6, .card-title');
          const cardTitleText = cardTitle ? cardTitle.textContent : 'Unknown';
          console.log(`Rendered card "${cardTitleText}": ${canvas.width}x${canvas.height}px`);
          
        } catch (err) {
          console.error('Failed to render card:', err, card);
          // Log which card failed
          const cardTitle = card.querySelector('.card-header h5, .card-header h6, .card-title');
          const cardTitleText = cardTitle ? cardTitle.textContent : 'Unknown';
          console.error('Failed card title:', cardTitleText);
          
          // Try to render just the card body if the full card fails
          const cardBody = card.querySelector('.card-body');
          if (cardBody) {
            try {
              console.log('Attempting to render card body only for:', cardTitleText);
              canvas = await window.html2canvas(cardBody, {
                scale: 2,
                useCORS: true,
                backgroundColor: '#ffffff',
                windowWidth: document.documentElement.scrollWidth,
                windowHeight: Math.max(document.documentElement.scrollHeight, cardBody.scrollHeight || 0),
                height: cardBody.scrollHeight || cardBody.offsetHeight,
                width: cardBody.scrollWidth || cardBody.offsetWidth,
                logging: false,
                removeContainer: false,
                allowTaint: true,
                ignoreElements: (element) => {
                  return element.tagName === 'SCRIPT' || element.tagName === 'IFRAME';
                }
              });
              
              if (!canvas || canvas.width === 0 || canvas.height === 0) {
                throw new Error('Card body canvas is empty or invalid');
              }
              
              console.log('Successfully rendered card body for:', cardTitleText, `${canvas.width}x${canvas.height}px`);
            } catch (bodyErr) {
              console.error('Failed to render card body:', bodyErr);
              continue; // Skip this card if both attempts fail
            }
          } else {
            continue; // Skip this card if rendering fails and no body to fallback to
          }
        }

        const imgW = pageW - margin * 2;
        const ratio = imgW / canvas.width;
        const imgH = canvas.height * ratio;

        // If card fits on one page, add it directly
        if (imgH <= availableHeight) {
          if (first) {
            addHeader(pageNum);
            first = false;
          }
          if (currentY + imgH > pageH - margin) {
            if (!first) addNewPage();
            first = false;
          }
          const imgData = canvas.toDataURL('image/jpeg', 0.92);
          pdf.addImage(imgData, 'JPEG', margin, currentY, imgW, imgH, undefined, 'FAST');
          currentY += imgH + 10;
        } else {
          // Card is too tall - split at row boundaries
          // Find table rows to use as break points (use bottom of each row)
          const tables = card.querySelectorAll('table');
          const rowBreakPoints = [];
          
          if (tables.length > 0) {
            // Get Y positions of table rows - calculate after canvas is rendered
            // We'll use the actual rendered positions
            tables.forEach(table => {
              const tbody = table.querySelector('tbody');
              if (tbody) {
                const rows = tbody.querySelectorAll('tr');
                rows.forEach((row, idx) => {
                  // Get row's position relative to card
                  const cardRect = card.getBoundingClientRect();
                  const rowRect = row.getBoundingClientRect();
                  // Use bottom of row as break point (so we break after the row, not in the middle)
                  const relativeY = rowRect.bottom - cardRect.top;
                  // Convert to canvas coordinates (accounting for scale of 2)
                  const canvasY = relativeY * 2;
                  rowBreakPoints.push({ y: canvasY, rowIndex: idx });
                });
              }
            });
            
            // Sort break points by Y position
            rowBreakPoints.sort((a, b) => a.y - b.y);
            
            // Filter out break points that are too close together (keep only unique Y positions)
            const filteredBreakPoints = [];
            let lastY = -1;
            for (const bp of rowBreakPoints) {
              if (bp.y - lastY > 3) { // Only keep break points that are at least 3px apart
                filteredBreakPoints.push(bp.y);
                lastY = bp.y;
              }
            }
            // Replace with simple array of Y values
            rowBreakPoints.length = 0;
            filteredBreakPoints.forEach(y => rowBreakPoints.push(y));
            
            console.log(`Card has ${rowBreakPoints.length} row break points for splitting`);
          }

          // If we have row break points, use them; otherwise use fixed page height
          let sourceY = 0;
          
          while (sourceY < canvas.height) {
            // Calculate remaining space on current page (in canvas pixels)
            const remainingPageSpace = (pageH - margin - currentY) / ratio;
            const remainingContentHeight = canvas.height - sourceY;
            
            // Check if ALL remaining content fits on current page
            if (remainingContentHeight <= remainingPageSpace) {
              // All remaining content fits - render it all without new page
              if (first) {
                addHeader(pageNum);
                first = false;
              }
              const finalHeight = remainingContentHeight * ratio;
              const finalCanvas = document.createElement('canvas');
              finalCanvas.width = canvas.width;
              finalCanvas.height = Math.ceil(remainingContentHeight);
              const finalCtx = finalCanvas.getContext('2d');
              finalCtx.drawImage(canvas, 0, sourceY, canvas.width, remainingContentHeight, 0, 0, canvas.width, remainingContentHeight);
              
              const finalImgData = finalCanvas.toDataURL('image/jpeg', 0.92);
              pdf.addImage(finalImgData, 'JPEG', margin, currentY, imgW, finalHeight, undefined, 'FAST');
              currentY += finalHeight + 10;
              break; // Done with this card
            }
            
            // Content doesn't fit - need to split at a row boundary
            // Initialize first page if needed
            if (first) {
              addHeader(pageNum);
              first = false;
            }
            
            // Find the best break point - fit as many COMPLETE rows as possible
            let nextBreakY = canvas.height;
            const maxY = sourceY + remainingPageSpace;
            
            // Find the last row break point that fits on current page
            if (rowBreakPoints.length > 0) {
              // Find ALL break points that fall in the range we can fit
              let bestBreakY = null;
              
              for (let bp = 0; bp < rowBreakPoints.length; bp++) {
                const breakY = rowBreakPoints[bp];
                // Skip break points before our current position
                if (breakY <= sourceY) continue;
                
                // Check if this break point fits on the current page
                if (breakY <= maxY) {
                  // This row completely fits, use it as candidate
                  bestBreakY = breakY;
                  // Keep going to find the LAST row that fits
                } else {
                  // This row doesn't fit, stop searching
                  break;
                }
              }
              
              if (bestBreakY && bestBreakY > sourceY) {
                // We found row(s) that fit completely - use the last one
                nextBreakY = bestBreakY;
              } else {
                // No complete row fits on this page - need to start new page
                // Find the first row break after current position
                let foundNext = false;
                for (let bp = 0; bp < rowBreakPoints.length; bp++) {
                  if (rowBreakPoints[bp] > sourceY) {
                    nextBreakY = rowBreakPoints[bp];
                    foundNext = true;
                    break;
                  }
                }
                
                // If we're at the start of the page and no row fits, 
                // we need to add a page break and try again
                if (!foundNext || nextBreakY === sourceY) {
                  // Force a page break and continue
                  addNewPage();
                  continue;
                }
              }
            } else {
              // No row break points - just split at page boundary
              nextBreakY = Math.min(maxY, canvas.height);
            }
            
            // Safety check - ensure we make progress
            if (nextBreakY <= sourceY) {
              console.warn('Invalid break point detected, forcing progress');
              nextBreakY = Math.min(sourceY + 100, canvas.height); // Move at least 100px forward
            }
            
            const sourceHeight = nextBreakY - sourceY;
            if (sourceHeight <= 0) break;
            
            const destHeight = sourceHeight * ratio;
            
            // Create canvas slice
            const pageCanvas = document.createElement('canvas');
            pageCanvas.width = canvas.width;
            pageCanvas.height = Math.ceil(sourceHeight);
            const ctx = pageCanvas.getContext('2d');
            ctx.drawImage(canvas, 0, sourceY, canvas.width, sourceHeight, 0, 0, canvas.width, sourceHeight);
            
            const pageImgData = pageCanvas.toDataURL('image/jpeg', 0.92);
            pdf.addImage(pageImgData, 'JPEG', margin, currentY, imgW, destHeight, undefined, 'FAST');
            currentY += destHeight;
            
            sourceY = nextBreakY;
            
            // Only add new page if there's more content to render
            if (sourceY < canvas.height) {
              addNewPage();
            }
          }
        }
      }

      // Restore original state
      setActiveSections(originalActiveSections);
      restoreCollapses.forEach((r) => {
        if (!r.shown) {
          r.el.classList.remove('show');
          r.el.style.height = '';
        }
      });

      // Build filename from Task ID
      const cleanTaskId = (taskId || 'review').toString().trim().replace(/\s+/g, '_').replace(/[^\w\-]+/g, '_');
      pdf.save(cleanTaskId + '_export.pdf');

    } catch (err) {
      console.error('PDF export failed:', err);
      alert('Sorry, the PDF could not be created. Check console for details.');
      
      // Restore state on error
      setActiveSections(originalActiveSections);
      restoreCollapses.forEach((r) => {
        if (!r.shown) {
          r.el.classList.remove('show');
          r.el.style.height = '';
        }
      });
    } finally {
      setExportingPdf(false);
    }
  };
  
  // Determine if fields should be locked
  const isLocked = () => {
    if (!data?.review) return false;
    const status = (data.review.status || '').toLowerCase();
    // Lock if completed or awaiting QC (but not if rework required)
    return (status.includes('completed') || status.includes('awaiting qc')) && !status.includes('rework');
  };
  
  const isReworkRequired = () => {
    if (!data?.review) return false;
    const status = (data.review.status || '').toLowerCase();
    return status.includes('rework required');
  };
  
  // Fetch AI SME referrals for this task
  const fetchAiSmeReferrals = async () => {
    try {
      setLoadingAiReferrals(true);
      const response = await fetch(`${BASE_URL}/api/my_referrals`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        // Filter referrals for this task
        const taskReferrals = (data.ai_sme_referrals || []).filter(
          ref => ref.task_id === taskId
        );
        setAiSmeReferrals(taskReferrals);
      }
    } catch (error) {
      console.error('Error loading AI SME referrals:', error);
    } finally {
      setLoadingAiReferrals(false);
    }
  };

  // Fetch Identity Verification (Sumsub) status
  const fetchIdentityVerification = async (applicantId = null) => {
    try {
      setLoadingIdentityVerification(true);
      const review = data?.review;
      const applicant_id = applicantId || review?.sumsub_applicant_id;
      
      if (!applicant_id) {
        setIdentityVerification(null);
        return;
      }

      const response = await fetch(
        `${BASE_URL}/api/sumsub/get_applicant_status/${applicant_id}`,
        { credentials: 'include' }
      );
      
      if (response.ok) {
        const verificationData = await response.json();
        setIdentityVerification(verificationData);
      } else {
        setIdentityVerification(null);
      }
    } catch (error) {
      console.error('Error loading identity verification:', error);
      setIdentityVerification(null);
    } finally {
      setLoadingIdentityVerification(false);
    }
  };

  // Helper function to auto-format date input with slashes
  const handleDateInput = (e, setter) => {
    let value = e.target.value.replace(/\D/g, ''); // Remove non-digits
    
    // Auto-insert slashes
    if (value.length >= 2) {
      value = value.slice(0, 2) + '/' + value.slice(2);
    }
    if (value.length >= 5) {
      value = value.slice(0, 5) + '/' + value.slice(5, 9);
    }
    
    setter(value);
  };

  // Helper function to validate dd/mm/yyyy date format
  const validateAndFormatDate = (dateStr) => {
    if (!dateStr) return null;
    
    try {
      // Remove any extra spaces
      dateStr = dateStr.trim();
      
      // Check if format is dd/mm/yyyy
      const datePattern = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/;
      const match = dateStr.match(datePattern);
      
      if (!match) {
        alert('Invalid date format. Please use DD/MM/YYYY format (e.g., 01/10/2025).');
        return null;
      }
      
      const [, day, month, year] = match;
      const date = new Date(year, month - 1, day);
      
      // Check if date is valid (handles cases like 31/02/2025)
      if (isNaN(date.getTime()) || 
          date.getDate() != day || 
          date.getMonth() != (month - 1) || 
          date.getFullYear() != year) {
        alert('Invalid date. Please enter a valid date.');
        return null;
      }
      
      // Check if date is not in the future
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (date > today) {
        if (!confirm('The date you entered is in the future. Do you want to save it anyway?')) {
          return null;
        }
      }
      
      // Return formatted as dd/mm/yyyy with leading zeros
      return `${String(day).padStart(2, '0')}/${String(month).padStart(2, '0')}/${year}`;
    } catch (err) {
      alert('Invalid date format. Please use DD/MM/YYYY format.');
      return null;
    }
  };

  // Manual save handlers with validation
  const handleSaveOutreachDate1 = async () => {
    const formattedDate = validateAndFormatDate(outreachDate1);
    if (!formattedDate) {
      return;
    }
    
    try {
      setSaving(true);
      const formData = new FormData();
      formData.append('outreach_date1', formattedDate);
      
      const response = await fetch(`${BASE_URL}/api/outreach/${taskId}/date1`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        // Refresh data to get updated chaser due dates
        await fetchTaskData();
        alert('Outreach date saved successfully.');
      } else {
        const errorData = await response.text();
        alert(`Failed to save outreach date: ${errorData}`);
      }
    } catch (err) {
      console.error('Error saving outreach date:', err);
      alert('Error saving outreach date. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveChaser = async (chaserNum, date) => {
    const formattedDate = validateAndFormatDate(date);
    if (!formattedDate) {
      return;
    }
    
    try {
      setSaving(true);
      const formData = new FormData();
      formData.append(`chaser${chaserNum}_issued`, formattedDate);
      
      const response = await fetch(`${BASE_URL}/api/outreach/${taskId}/chasers`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        await fetchTaskData();
        alert(`Chaser ${chaserNum} date saved successfully.`);
      } else {
        const errorData = await response.text();
        alert(`Failed to save chaser date: ${errorData}`);
      }
    } catch (err) {
      console.error('Error saving chaser date:', err);
      alert('Error saving chaser date. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNTC = async () => {
    const formattedDate = validateAndFormatDate(ntcDate);
    if (!formattedDate) {
      return;
    }
    
    try {
      setSaving(true);
      const formData = new FormData();
      formData.append('ntc_issued', formattedDate);
      
      const response = await fetch(`${BASE_URL}/api/outreach/${taskId}/chasers`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        await fetchTaskData();
        alert('NTC date saved successfully.');
      } else {
        const errorData = await response.text();
        alert(`Failed to save NTC date: ${errorData}`);
      }
    } catch (err) {
      console.error('Error saving NTC date:', err);
      alert('Error saving NTC date. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleOutreachCompleteChange = async (e) => {
    const isChecked = e.target.checked;
    
    try {
      setSaving(true);
      const formData = new FormData();
      formData.append('outreach_complete', isChecked ? '1' : '0');
      
      const response = await fetch(`${BASE_URL}/api/outreach/${taskId}/complete`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        // Refresh data to see updated status
        await fetchTaskData();
      } else {
        alert('Failed to update outreach status. Please try again.');
        e.target.checked = !isChecked; // Revert checkbox
      }
    } catch (err) {
      console.error('Error saving outreach complete:', err);
      alert('Error updating outreach status. Please try again.');
      e.target.checked = !isChecked; // Revert checkbox
    } finally {
      setSaving(false);
    }
  };

  // Decision section handlers
  const handleSaveProgress = async () => {
    if (saving) return;
    
    try {
      setSaving(true);
      
      // Collect form data from the DOM (using refs would be better, but this works)
      const formData = new FormData();
      formData.append('outcome', document.querySelector('[name="outcome"]')?.value || '');
      formData.append('rationale', document.querySelector('[name="rationale"]')?.value || '');
      formData.append('financial_crime_reason', document.querySelector('[name="financial_crime_reason"]')?.value || '');
      formData.append('sme_query', document.querySelector('[name="sme_query"]')?.value || '');
      formData.append('case_summary', document.querySelector('[name="case_summary"]')?.value || '');
      
      const response = await fetch(`${BASE_URL}/api/reviewer_panel/${taskId}/save_progress`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        alert('Progress saved successfully.');
        await fetchTaskData(); // Refresh data
      } else {
        const errorData = await response.json();
        alert(`Failed to save progress: ${errorData.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Error saving progress:', err);
      alert('Error saving progress. Please try again.');
    } finally {
      setSaving(false);
    }
  };
  
  const handleSubmit = async () => {
    if (saving) return;
    
    try {
      setSaving(true);
      
      // Collect form data
      const formData = new FormData();
      formData.append('outcome', document.querySelector('[name="outcome"]')?.value || '');
      formData.append('rationale', document.querySelector('[name="rationale"]')?.value || '');
      formData.append('financial_crime_reason', document.querySelector('[name="financial_crime_reason"]')?.value || '');
      formData.append('case_summary', document.querySelector('[name="case_summary"]')?.value || '');
      
      const response = await fetch(`${BASE_URL}/api/reviewer_panel/${taskId}/submit`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        alert('Review submitted successfully.');
        await fetchTaskData(); // Refresh data
      } else {
        const errorData = await response.json();
        alert(`Failed to submit: ${errorData.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Error submitting review:', err);
      alert('Error submitting review. Please try again.');
    } finally {
      setSaving(false);
    }
  };
  
  const handleReferSME = async () => {
    if (saving) return;
    
    // Show the SME Query box when button is clicked (if not already shown)
    if (!showSmeQuery) {
      setShowSmeQuery(true);
      // Scroll to the SME Query box
      setTimeout(() => {
        const smeQueryElement = document.querySelector('[name="sme_query"]');
        if (smeQueryElement) {
          smeQueryElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          smeQueryElement.focus();
        }
      }, 100);
      return; // Don't submit yet, just show the box
    }
    
    // If box is already visible, proceed with submission
    try {
      setSaving(true);
      
      // Collect form data
      const smeQuery = document.querySelector('[name="sme_query"]')?.value || '';
      
      if (!smeQuery.trim()) {
        alert('Please provide an SME Query before referring.');
        setSaving(false);
        return;
      }
      
      // If AI SME is enabled, route to AI SME chat
      if (isModuleEnabled('ai_sme')) {
        const basePath = window.location.pathname.startsWith('/qc_review/') 
          ? `/qc_review/${taskId}/sme`
          : `/view_task/${taskId}/sme`;
        navigate(basePath);
        return;
      }
      
      // If AI SME is disabled, use manual referral
      const formData = new FormData();
      formData.append('sme_query', smeQuery);
      
      const response = await fetch(`${BASE_URL}/api/reviewer_panel/${taskId}/refer_sme`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        alert('Successfully referred to SME for technical guidance.');
        await fetchTaskData(); // Refresh data
        
        // Navigate to SME view
        setTimeout(() => {
          const basePath = window.location.pathname.startsWith('/qc_review/') 
            ? `/qc_review/${taskId}`
            : `/view_task/${taskId}`;
          navigate(basePath);
        }, 500);
      } else {
        const errorData = await response.json();
        alert(`Failed to refer to SME: ${errorData.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Error referring to SME:', err);
      alert('Error referring to SME. Please try again.');
    } finally {
      setSaving(false);
    }
  };
  
  const generateCaseSummary = () => {
    const parts = [];
    
    // Get data from database (includes all previously saved values)
    const review = data?.review || {};
    
    // Helper function to get value: prefer DOM (if it has a value), otherwise use database value
    // This ensures we get all previously saved data even if DOM fields are empty
    const getValue = (fieldName, dbValue = '') => {
      const domElement = document.querySelector(`[name="${fieldName}"]`);
      // If DOM element exists and has a non-empty value, use it (user may have just changed it)
      if (domElement && domElement.value && domElement.value.trim()) {
        return domElement.value.trim();
      }
      // Otherwise, use database value (includes all previously saved data)
      return (dbValue || '').trim();
    };
    
    // DDG sections mapping
    const ddgSectionMap = {
      'idv': 'IDV',
      'nob': 'NOB',
      'income': 'Income',
      'expenditure': 'Expenditure',
      'structure': 'Structure',
      'ta': 'TA',
      'sof': 'SOF',
      'sow': 'SOW'
    };
    
    // Collect DDG section rationales - use database values as base, override with DOM if present
    try {
      const ddgFields = ['idv', 'nob', 'income', 'expenditure', 'structure', 'ta', 'sof', 'sow'];
      ddgFields.forEach((fieldKey) => {
        const fieldName = `${fieldKey}_rationale`;
        const dbValue = review[fieldName] || '';
        const value = getValue(fieldName, dbValue);
        
        if (value) {
          const sectionLabel = ddgSectionMap[fieldKey] || fieldKey.toUpperCase();
          parts.push(`${sectionLabel}: ${value}`);
        }
      });
      
      // SAR and DAML rationales
      const sarValue = getValue('sar_rationale', review.sar_rationale || '');
      if (sarValue) {
        parts.push(`SAR: ${sarValue}`);
      }
      
      const damlValue = getValue('daml_rationale', review.daml_rationale || '');
      if (damlValue) {
        parts.push(`DAML: ${damlValue}`);
      }
    } catch (e) {
      console.warn('Error collecting DDG rationales:', e);
    }
    
    // Financial Crime concern rationales - try to get from DOM first, then database
    try {
      const concernAreas = document.querySelectorAll('textarea[name^="concern_"][name$="_rationale"]');
      const processedConcerns = new Set();
      
      concernAreas.forEach((area) => {
        const name = area.getAttribute('name') || '';
        const row = area.closest('tr');
        let label = '';
        if (row) {
          const firstCell = row.querySelector('td:first-child');
          if (firstCell) {
            const ro = firstCell.querySelector('input[readonly], input.form-control-plaintext');
            label = ro ? (ro.value || ro.textContent || '').trim() : (firstCell.textContent || '').trim();
          }
        }
        const rationale = (area.value || '').trim();
        if (rationale) {
          parts.push(label ? `${label}: ${rationale}` : rationale);
          processedConcerns.add(name);
        }
      });
      
      // Also check database for any concern rationales not in DOM
      Object.keys(review).forEach((key) => {
        if (key.startsWith('concern_') && key.endsWith('_rationale') && !processedConcerns.has(key)) {
          const value = (review[key] || '').trim();
          if (value) {
            // Try to extract label from key or use key as label
            const label = key.replace('concern_', '').replace('_rationale', '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            parts.push(`${label}: ${value}`);
          }
        }
      });
    } catch (e) {
      console.warn('Error collecting concern rationales:', e);
    }
    
    // Primary rationale and overall rationale - use database values as base
    const primaryRationale = getValue('primary_rationale', review.primary_rationale || '');
    const overallRationale = getValue('rationale', review.rationale || '');
    if (primaryRationale) parts.unshift(`Primary Rationale: ${primaryRationale}`);
    if (overallRationale) parts.push(`Overall Rationale: ${overallRationale}`);
    
    // Decision outcome and rationale - use database values as base
    const outcome = getValue('outcome', review.outcome || '');
    const decisionRationale = getValue('rationale', review.rationale || '');
    
    // Remove previously-added generic "Overall Rationale" if present to avoid duplication
    for (let i = parts.length - 1; i >= 0; i--) {
      if (typeof parts[i] === 'string' && parts[i].indexOf('Overall Rationale:') === 0) {
        parts.splice(i, 1);
      }
    }
    
    if (outcome) parts.unshift(`Decision Outcome: ${outcome}`);
    if (decisionRationale) parts.splice(1, 0, `Decision Rationale: ${decisionRationale}`);
    
    return parts.filter(Boolean).join('\n\n');
  };

  const handleReworkComplete = async () => {
    if (saving) return;
    
    try {
      setSaving(true);
      
      // Collect form data like the submit button does
      const formData = new FormData();
      formData.append('outcome', document.querySelector('[name="outcome"]')?.value || '');
      formData.append('rationale', document.querySelector('[name="rationale"]')?.value || '');
      formData.append('financial_crime_reason', document.querySelector('[name="financial_crime_reason"]')?.value || '');
      formData.append('case_summary', document.querySelector('[name="case_summary"]')?.value || '');
      
      const response = await fetch(`${BASE_URL}/api/reviewer_panel/${taskId}/rework_complete`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          alert('Rework marked as complete. Task resubmitted for QC review.');
          await fetchTaskData(); // Refresh data
        } else {
          alert(`Failed to mark rework as complete: ${result.error || 'Unknown error'}`);
        }
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to mark rework as complete' }));
        alert(`Failed to mark rework as complete: ${errorData.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Error marking rework as complete:', err);
      alert('Error marking rework as complete. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateCaseSummary = async (e) => {
    const btn = e?.target || e?.currentTarget;
    const originalHTML = btn ? btn.innerHTML : '';
    
    try {
      // Generate the case summary
      const summary = generateCaseSummary();
      
      if (!summary || !summary.trim()) {
        alert('No content available to generate case summary. Please fill in some rationales or decision information.');
        return;
      }
      
      // Update the textarea
      const textarea = document.querySelector('textarea[name="case_summary"]');
      if (textarea) {
        textarea.value = summary;
        // Trigger change event
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        textarea.dispatchEvent(new Event('change', { bubbles: true }));
      }
      
      // Update button to show loading state
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving...';
      }
      
      // Save to backend using the same API as Save Section button
      const formData = new FormData();
      formData.append('case_summary', summary);
      
      // Use the same save_progress endpoint that Save Section button uses
      const response = await fetch(`${BASE_URL}/api/reviewer_panel/${taskId}/save_progress`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          // Update local state
          setDecisionData(prev => ({ ...prev, case_summary: summary }));
          // Show success feedback
          if (btn) {
            btn.classList.remove('btn-outline-secondary');
            btn.classList.add('btn-success');
            btn.innerHTML = '<i class="bi bi-check2-circle"></i> Summary Saved';
            setTimeout(() => {
              btn.classList.remove('btn-success');
              btn.classList.add('btn-outline-secondary');
              btn.innerHTML = originalHTML;
              btn.disabled = false;
            }, 2000);
          }
        } else {
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHTML;
          }
          alert('Summary created but could not be saved. Please save manually.');
        }
      } else {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalHTML;
        }
        alert('Summary created but could not be saved. Please save manually.');
      }
    } catch (error) {
      console.error('Error creating case summary:', error);
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
      }
      alert('Error creating case summary. Please try again.');
    }
  };

  const handleSaveDDG = async () => {
    if (saving) return;
    
    try {
      setSaving(true);
      
      // Collect all DDG section data
      const formData = new FormData();
      const ddgSections = ['idv', 'nob', 'income', 'expenditure', 'structure', 'ta', 'sof', 'sow'];
      
      ddgSections.forEach(section => {
        const rationale = document.querySelector(`[name="${section}_rationale"]`)?.value || '';
        const outreachRequired = document.querySelector(`[name="${section}_outreach_required"]`)?.checked ? '1' : '0';
        const sectionCompleted = document.querySelector(`[name="${section}_section_completed"]`)?.checked ? '1' : '0';
        
        formData.append(`${section}_rationale`, rationale);
        formData.append(`${section}_outreach_required`, outreachRequired);
        formData.append(`${section}_section_completed`, sectionCompleted);
      });
      
      // FinCrime concerns
      formData.append('sar_rationale', document.querySelector('[name="sar_rationale"]')?.value || '');
      formData.append('sar_date_raised', document.querySelector('[name="sar_date_raised"]')?.value || '');
      formData.append('daml_rationale', document.querySelector('[name="daml_rationale"]')?.value || '');
      formData.append('daml_date_raised', document.querySelector('[name="daml_date_raised"]')?.value || '');
      
      const response = await fetch(`${BASE_URL}/api/reviewer_panel/${taskId}/save_ddg`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (response.ok) {
        alert('DDG section saved successfully.');
        await fetchTaskData(); // Refresh data
      } else {
        const errorData = await response.json();
        alert(`Failed to save DDG section: ${errorData.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Error saving DDG section:', err);
      alert('Error saving DDG section. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const fetchTaskData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `${BASE_URL}/api/reviewer_panel/${taskId}`,
        {
          credentials: 'include',
          headers: { 'Accept': 'application/json' },
        }
      );

      if (!response.ok) {
        if (response.status === 404) throw new Error('Task not found');
        if (response.status === 403) throw new Error('Access denied');
        throw new Error(`HTTP ${response.status}`);
      }

      const taskData = await response.json();
      setData(taskData);
      // Initialize selected outcome from loaded data
      if (taskData?.review?.outcome) {
        setSelectedOutcome(taskData.review.outcome);
      }
      // Fetch identity verification if applicant ID exists
      if (taskData?.review?.sumsub_applicant_id) {
        // Use setTimeout to ensure data state is updated first
        setTimeout(() => {
          fetchIdentityVerification(taskData.review.sumsub_applicant_id);
        }, 100);
      }
      // Initialize outreach dates
      setOutreachDate1(taskData?.review?.OutreachDate1 || '');
      setChaser1Date(taskData?.review?.Chaser1IssuedDate || '');
      setChaser2Date(taskData?.review?.Chaser2IssuedDate || '');
      setChaser3Date(taskData?.review?.Chaser3IssuedDate || '');
      setNtcDate(taskData?.review?.NTCIssuedDate || '');
      // Initialize decision data
      setDecisionData({
        outcome: taskData?.review?.outcome || '',
        rationale: taskData?.review?.rationale || '',
        financial_crime_reason: taskData?.review?.financial_crime_reason || taskData?.review?.fincrime_reason || '',
        sme_query: taskData?.review?.sme_query || '',
        case_summary: taskData?.review?.case_summary || ''
      });
      // Show SME Query box if query already exists or if task was referred to SME
      if (taskData?.review?.sme_query || taskData?.review?.referred_to_sme) {
        setShowSmeQuery(true);
      }
    } catch (err) {
      console.error('Error fetching task data:', err);
      setError(err.message || 'Failed to load task');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container my-4">
        <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container my-4">
        <div className="alert alert-danger">
          <h4 className="alert-heading">Error</h4>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={() => navigate(-1)}>
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const review = data?.review || {};
  const match = data?.match || {};

  // Helper function to normalize status display
  const getDisplayStatus = (status) => {
    if (!status) return 'Pending';
    // Don't normalize "Outreach Complete" - show it as is
    if (status.toLowerCase() === 'outreach complete') {
      return 'Outreach Complete';
    }
    // If status contains "Chaser" or "Outreach" (but not "Outreach Complete"), show as "Outreach"
    if (status.toLowerCase().includes('chaser') || (status.toLowerCase().includes('outreach') && !status.toLowerCase().includes('complete'))) {
      return 'Outreach';
    }
    return status;
  };

  // Get all customer detail fields (cd_* fields)
  const customerFields = Object.keys(review).filter(key => key.startsWith('cd_'));
  
  // Get all entity fields
  const entityFields = Object.keys(review).filter(key => 
    key.startsWith('entity_') || key.startsWith('lp1_')
  );

  // DDG sections
  const status = getDisplayStatus(review.status);
  const statusClass = 
    status.toLowerCase() === 'outreach complete' ? 'success' :
    status.toLowerCase().includes('complete') && status.toLowerCase() !== 'outreach complete' ? 'success' :
    status.toLowerCase().includes('pending') || status.toLowerCase().includes('awaiting') || status.toLowerCase() === 'outreach' ? 'warning' :
    status.toLowerCase().includes('rework') || status.toLowerCase().includes('referred') ? 'danger' :
    'secondary';

  const ddgSections = [
    { label: 'ID&V', key: 'idv' },
    { label: 'NoB', key: 'nob' },
    { label: 'Expected Income', key: 'income' },
    { label: 'Expenditure', key: 'expenditure' },
    { label: 'Structure', key: 'structure' },
    { label: 'TA', key: 'ta' },
    { label: 'SoF', key: 'sof' },
    { label: 'SoW', key: 'sow' }
  ];

  const renderField = (label, value) => (
    <tr key={label}>
      <td className="fw-semibold">{label}</td>
      <td>{value || '—'}</td>
    </tr>
  );

  const renderCustomerDetailsSection = () => {
    // Define the customer detail fields using actual field names from database
    const fields = [
      { label: 'Entity Type', original: 'entity_type_original', enriched: 'entity_type_enriched' },
      { label: 'Entity Name', original: 'entity_name_original', enriched: 'entity_name_enriched' },
      { label: 'Entity Trading Name', original: 'entity_trading_name_original', enriched: 'entity_trading_name_enriched' },
      { label: 'Entity Registration Number', original: 'entity_registration_number_original', enriched: 'entity_registration_number_enriched' },
      { label: 'Entity Incorporation Date', original: 'entity_incorp_date_original', enriched: 'entity_incorp_date_enriched' },
      { label: 'Entity Status', original: 'entity_status_original', enriched: 'entity_status_enriched' },
      { label: 'Address Line 1', original: 'address_line1_original', enriched: 'address_line1_enriched' },
      { label: 'Address Line 2', original: 'address_line2_original', enriched: 'address_line2_enriched' },
      { label: 'City', original: 'city_original', enriched: 'city_enriched' },
      { label: 'Postcode', original: 'postcode_original', enriched: 'postcode_enriched' },
      { label: 'Country', original: 'country_original', enriched: 'country_enriched' },
      { label: 'Phone', original: 'primary_phone' },
      { label: 'Email', original: 'primary_email' },
      { label: 'SIC Codes', original: 'sic_codes_original', enriched: 'sic_codes_enriched' },
      { label: 'Accounts Balance', original: 'existing_accounts_balance' },
      { label: 'Expected Annual Revenue', original: 'expected_annual_revenue' },
      { label: 'Expected Money into Account', original: 'expected_money_in_account' },
      { label: 'Expected Revenue Sources', original: 'expected_revenue_sources' },
      { label: 'Expected Transaction Jurisdictions', original: 'expected_txn_jurisdictions' },
      { label: 'Linked Party Full Name 1', original: 'lp1_full_name_original', enriched: 'lp1_full_name_enriched' },
      { label: 'Linked Party Role 1', original: 'lp1_role_original', enriched: 'lp1_role_enriched' },
      { label: 'Linked Party DoB 1', original: 'lp1_dob_original', enriched: 'lp1_dob_enriched' },
      { label: 'Linked Party Nationality 1', original: 'lp1_nationality_original', enriched: 'lp1_nationality_enriched' },
      { label: 'Linked Party Country of Residence 1', original: 'lp1_country_residence_original', enriched: 'lp1_country_residence_enriched' },
      { label: 'Linked Party Address 1', original: 'lp1_correspondence_address_original', enriched: 'lp1_correspondence_address_enriched' },
      { label: 'Linked Party Appointed On 1', original: 'lp1_appointed_on_original', enriched: 'lp1_appointed_on_enriched' }
    ];

    // Also get all other customer-related fields from review/match that aren't in the hardcoded list
    const allCustomerFields = {};
    const excludeKeys = ['task_id', 'match_id', 'id', 'total_score', 'match_score', 
                         'match_explanation', 'created_at', 'updated_at', 'watchlist_id',
                         'status', 'outcome', 'rationale', 'assigned_to', 'completed_by',
                         'qc_assigned_to', 'qc_outcome', 'qc_comment', 'qc_rework_required'];
    
    // Get all fields from review that look like customer data
    Object.keys(review).forEach(key => {
      if (!excludeKeys.includes(key) && 
          (key.includes('customer') || key.includes('phone') || key.includes('email') || 
           key.startsWith('cd_') || key.startsWith('entity_') || key.startsWith('lp1_') ||
           key.includes('address') || key.includes('city') || key.includes('postcode') ||
           key.includes('country') || key.includes('sic') || key.includes('revenue') ||
           key.includes('account') || key.includes('transaction') || key.includes('jurisdiction'))) {
        // Check if this field is not already in the hardcoded fields list
        const isInHardcodedList = fields.some(f => 
          f.original === key || f.enriched === key
        );
        if (!isInHardcodedList && review[key] && review[key] !== '' && review[key] !== 'None' && review[key] !== 'null') {
          allCustomerFields[key] = review[key];
        }
      }
    });

    return (
      <div className="table-responsive">
        <table className="table table-sm">
          <thead className="table-light">
            <tr>
              <th style={{width: '40%'}}>Field</th>
              <th style={{width: '20%'}}>Source</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {fields
              .filter(field => {
                // Check visibility for both original and enriched fields
                const originalVisible = isFieldVisible(field.original);
                const enrichedVisible = field.enriched ? isFieldVisible(field.enriched) : true;
                return originalVisible || enrichedVisible;
              })
              .map(field => {
                const originalValue = review[field.original];
                const enrichedValue = field.enriched ? review[field.enriched] : null;
                const showEnriched = enrichedValue && enrichedValue !== '' && enrichedValue !== 'None' && enrichedValue !== 'null';
                const originalVisible = isFieldVisible(field.original);
                const enrichedVisible = field.enriched ? isFieldVisible(field.enriched) : true;
                
                // Skip if neither original nor enriched is visible
                if (!originalVisible && !enrichedVisible) {
                  return null;
                }
                
                return (
                  <React.Fragment key={field.label}>
                    {originalVisible && (
                      <tr>
                        {showEnriched && enrichedVisible && <td rowSpan="2">{field.label}</td>}
                        {(!showEnriched || !enrichedVisible) && <td>{field.label}</td>}
                        <td>Original</td>
                        <td>
                          <input 
                            type="text" 
                            className="form-control form-control-sm" 
                            value={originalValue || ''} 
                            readOnly 
                          />
                        </td>
                      </tr>
                    )}
                    {showEnriched && enrichedVisible && (
                      <tr>
                        {!originalVisible && <td>{field.label}</td>}
                        <td>Enriched</td>
                        <td>
                          <input 
                            type="text" 
                            className="form-control form-control-sm" 
                            value={enrichedValue} 
                            readOnly 
                          />
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            {/* Display additional customer fields that aren't in the hardcoded list */}
            {Object.entries(allCustomerFields)
              .filter(([key]) => isFieldVisible(key))
              .map(([key, value]) => (
                <tr key={key}>
                  <td>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                  <td>Source</td>
                  <td>
                    <input 
                      type="text" 
                      className="form-control form-control-sm" 
                      value={value || ''} 
                      readOnly 
                    />
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    );
  };

  // Check permissions - can_view allows access, can_edit allows interactions
  // Check both "review_tasks" and "review" (in case database uses "review")
  const canViewTasks = canView('review_tasks') || canView('review');
  const canEditTasks = canEdit('review_tasks') || canEdit('review');
  
  if (!canViewTasks) {
    return (
      <div className="container my-4">
        <div className="alert alert-warning">
          <h4 className="alert-heading">Access Denied</h4>
          <p>You do not have permission to view tasks.</p>
          <p className="mb-0">Please contact your administrator if you believe this is an error.</p>
        </div>
      </div>
    );
  }

  // Don't wrap in BaseLayout here - it's already wrapped in App.jsx routes
  return (
    <>
      <div className="container-fluid my-4 px-5">
        <h2 style={{fontWeight: '800', letterSpacing: '.2px'}}>Review Panel - Entity</h2>
      
        <div className="row g-4">
          {/* Main Content */}
          <div className="col-lg-9 case-main">
            {/* Case Summary */}
            <div className="card shadow-sm mb-4">
              <div className="card-body">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h2 className="h6 mb-0">Case Summary</h2>
                  <button 
                    onClick={handleExportPdf}
                    disabled={exportingPdf || !pdfLibsReady}
                    className="btn btn-sm btn-outline-primary"
                    title={!pdfLibsReady ? 'PDF libraries loading...' : 'Export review as PDF'}
                  >
                    {exportingPdf ? (
                      <>
                        <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                        Building PDF…
                      </>
                    ) : (
                      <>
                        <i className="bi bi-file-earmark-pdf"></i> Export PDF
                      </>
                    )}
                  </button>
                </div>
                <table className="table table-sm table-borderless mb-0">
                  <tbody>
                    {renderField('Task ID', taskId)}
                    {renderField('Customer ID', review.customer_id || '—')}
                    {renderField('Task Type', review.hit_type || review.record_type)}
                    <tr>
                      <td className="fw-semibold">Status</td>
                      <td>
                        <span className={`badge bg-${statusClass}`}>{status}</span>
                      </td>
                    </tr>
                    {renderField('Assigned To', (() => {
                      const assignedToId = review.assigned_to;
                      if (!assignedToId) return 'Unassigned';
                      const userName = data?.users?.[assignedToId.toString()];
                      return userName || review.assigned_to_name || `User ${assignedToId}`;
                    })())}
                    {renderField('Current Risk Rating', review.currentriskrating)}
                    {renderField('Match Score', review.total_score)}
                    {renderField('Last Updated', review.updated_at ? new Date(review.updated_at).toLocaleString() : '—')}
                        {renderField('Date Completed', (() => {
                          const dateStr = review.date_completed;
                          return dateStr ? new Date(dateStr).toLocaleString() : '—';
                        })())}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Customer Details */}
            <div className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <h5 className="mb-0">Customer Details</h5>
                <button 
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('customer')) {
                      newSections.delete('customer');
                    } else {
                      newSections.add('customer');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('customer') && (
                <div className="card-body">
                  {renderCustomerDetailsSection()}
                </div>
              )}
            </div>

            {/* Due Diligence Review */}
            <div className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <h5 className="mb-0">Due Diligence - Review</h5>
                <button 
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('ddg')) {
                      newSections.delete('ddg');
                    } else {
                      newSections.add('ddg');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('ddg') && (
                <div className="card-body">
                  {/* DDG Sections Table */}
                  <div className="table-responsive mb-4">
                    <table className="table table-sm">
                      <thead className="table-light">
                        <tr>
                          <th style={{width: '20%'}}>Section</th>
                          <th>Rationale</th>
                          <th style={{width: '16%'}}>Outreach Req.</th>
                          <th style={{width: '16%'}}>Section Complete</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ddgSections.map(section => (
                          <tr key={section.key}>
                            <td>{section.label}</td>
                            <td>
                              <textarea 
                                name={`${section.key}_rationale`}
                                className="form-control form-control-sm" 
                                rows="2" 
                                defaultValue={review[`${section.key}_rationale`] || ''}
                                disabled={saving || isLocked() || !canEditTasks}
                              />
                            </td>
                            <td className="text-center">
                              <input 
                                name={`${section.key}_outreach_required`}
                                type="checkbox" 
                                className="form-check-input" 
                                defaultChecked={review[`${section.key}_outreach_required`] == 1}
                                disabled={saving || isLocked() || !canEditTasks}
                              />
                            </td>
                            <td className="text-center">
                              <input 
                                name={`${section.key}_section_completed`}
                                type="checkbox" 
                                className="form-check-input" 
                                defaultChecked={review[`${section.key}_section_completed`] == 1}
                                disabled={saving || isLocked() || !canEditTasks}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  
                  {/* FinCrime Concerns Table */}
                  <div className="table-responsive">
                    <table className="table table-sm">
                      <thead className="table-light">
                        <tr>
                          <th style={{width: '25%'}}>FinCrime Concern</th>
                          <th>Rationale</th>
                          <th style={{width: '20%'}}>Date Raised</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>SAR</td>
                          <td>
                            <textarea 
                              name="sar_rationale"
                              className="form-control form-control-sm" 
                              rows="2" 
                              defaultValue={review.sar_rationale || ''}
                              disabled={saving || !canEditTasks}
                            />
                          </td>
                          <td>
                            <input 
                              name="sar_date_raised"
                              type="date" 
                              className="form-control form-control-sm" 
                              defaultValue={review.sar_date_raised || ''}
                              disabled={saving || !canEditTasks}
                            />
                          </td>
                        </tr>
                        <tr>
                          <td>DAML</td>
                          <td>
                            <textarea 
                              name="daml_rationale"
                              className="form-control form-control-sm" 
                              rows="2" 
                              defaultValue={review.daml_rationale || ''}
                              disabled={saving || !canEditTasks}
                            />
                          </td>
                          <td>
                            <input 
                              name="daml_date_raised"
                              type="date" 
                              className="form-control form-control-sm" 
                              defaultValue={review.daml_date_raised || ''}
                              disabled={saving || !canEditTasks}
                            />
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  {/* Save Section Button for DDG */}
                  <div className="d-flex justify-content-end mt-3">
                    <button 
                      type="button"
                      className="btn btn-sm btn-primary"
                      onClick={handleSaveDDG}
                      disabled={saving || !canEditTasks}
                    >
                      <i className="bi bi-save"></i> Save Section
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Screening */}
            <div className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <h5 className="mb-0">Screening</h5>
                <button 
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('screening')) {
                      newSections.delete('screening');
                    } else {
                      newSections.add('screening');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('screening') && (
                <div className="card-body">
                  <div className="table-responsive">
                    <table className="table table-sm">
                      <thead className="table-light">
                        <tr>
                          <th style={{width: '30%'}}>Screening Type</th>
                          <th>Outcome</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Sanctions</td>
                          <td>
                            <input 
                              type="text" 
                              className="form-control form-control-sm" 
                              defaultValue={review.sanctionsscreeningoutcome || review.sanctions_outcome || ''}
                            />
                          </td>
                        </tr>
                        <tr>
                          <td>PEPs & RCAs</td>
                          <td>
                            <input 
                              type="text" 
                              className="form-control form-control-sm" 
                              defaultValue={review.RCPEPscreeningoutcome || review.pep_rca_outcome || ''}
                            />
                          </td>
                        </tr>
                        <tr>
                          <td>Adverse Media</td>
                          <td>
                            <input 
                              type="text" 
                              className="form-control form-control-sm" 
                              defaultValue={review.AMscreeningoutcome || review.adverse_media_outcome || ''}
                            />
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Outreach */}
            <div className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <h5 className="mb-0">Outreach</h5>
                <button 
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('outreach')) {
                      newSections.delete('outreach');
                    } else {
                      newSections.add('outreach');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('outreach') && (
                <div className="card-body">
                  {saving && (
                    <div className="alert alert-info py-1 mb-2">
                      <small>Saving...</small>
                    </div>
                  )}
                  {!review.OutreachDate1 ? (
                    <>
                      {/* Initial Outreach Form */}
                      <div className="mb-3">
                        <label className="form-label fw-semibold">Outreach Date 1</label>
                        <div className="input-group">
                          <input 
                            type="text" 
                            className="form-control" 
                            placeholder="DD/MM/YYYY"
                            value={outreachDate1}
                            onChange={(e) => handleDateInput(e, setOutreachDate1)}
                            maxLength="10"
                            disabled={saving || !canEditTasks}
                          />
                          <button 
                            className="btn btn-primary" 
                            type="button"
                            onClick={handleSaveOutreachDate1}
                            disabled={saving || !outreachDate1 || !canEditTasks}
                          >
                            Save
                          </button>
                        </div>
                      </div>

                      <div className="form-check mt-3">
                        <input 
                          type="checkbox" 
                          className="form-check-input" 
                          id="outreach_complete"
                          defaultChecked={review.outreach_complete}
                          onChange={handleOutreachCompleteChange}
                          disabled={saving || !canEditTasks}
                        />
                        <label className="form-check-label fw-semibold" htmlFor="outreach_complete">
                          Outreach Complete
                        </label>
                      </div>
                    </>
                  ) : (
                    <>
                      {/* Outreach Recorded - Show Chaser Table */}
                      <div className="mb-3">
                        <div className="small text-muted">
                          First outreach recorded: {review.OutreachDate1}
                        </div>
                      </div>

                      <div className="table-responsive">
                        <table className="table table-sm align-middle">
                          <thead className="table-light small">
                            <tr>
                              <th style={{width: '33.333%'}}>Chaser Cycle</th>
                              <th style={{width: '33.333%'}}>Due</th>
                              <th style={{width: '33.333%'}}>Issued</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td>1</td>
                              <td>{review.Chaser1DueDate || '—'}</td>
                              <td>
                                {review.Chaser1IssuedDate ? (
                                  <input type="text" className="form-control form-control-sm" value={review.Chaser1IssuedDate} readOnly />
                                ) : (
                                  <div className="input-group input-group-sm">
                                    <input 
                                      type="text" 
                                      className="form-control form-control-sm" 
                                      placeholder="DD/MM/YYYY"
                                      value={chaser1Date}
                                      onChange={(e) => handleDateInput(e, setChaser1Date)}
                                      maxLength="10"
                                      disabled={saving || !canEditTasks}
                                    />
                                    <button 
                                      className="btn btn-primary btn-sm" 
                                      type="button"
                                      onClick={() => handleSaveChaser(1, chaser1Date)}
                                      disabled={saving || !chaser1Date || !canEditTasks}
                                    >
                                      Save
                                    </button>
                                  </div>
                                )}
                              </td>
                            </tr>
                            <tr>
                              <td>2</td>
                              <td>{review.Chaser2DueDate || '—'}</td>
                              <td>
                                {review.Chaser2IssuedDate ? (
                                  <input type="text" className="form-control form-control-sm" value={review.Chaser2IssuedDate} readOnly />
                                ) : (
                                  <div className="input-group input-group-sm">
                                    <input 
                                      type="text" 
                                      className="form-control form-control-sm" 
                                      placeholder="DD/MM/YYYY"
                                      value={chaser2Date}
                                      onChange={(e) => handleDateInput(e, setChaser2Date)}
                                      maxLength="10"
                                      disabled={!review.Chaser1IssuedDate || saving || !canEditTasks}
                                    />
                                    <button 
                                      className="btn btn-primary btn-sm" 
                                      type="button"
                                      onClick={() => handleSaveChaser(2, chaser2Date)}
                                      disabled={!review.Chaser1IssuedDate || saving || !chaser2Date}
                                    >
                                      Save
                                    </button>
                                  </div>
                                )}
                              </td>
                            </tr>
                            <tr>
                              <td>3</td>
                              <td>{review.Chaser3DueDate || '—'}</td>
                              <td>
                                {review.Chaser3IssuedDate ? (
                                  <input type="text" className="form-control form-control-sm" value={review.Chaser3IssuedDate} readOnly />
                                ) : (
                                  <div className="input-group input-group-sm">
                                    <input 
                                      type="text" 
                                      className="form-control form-control-sm" 
                                      placeholder="DD/MM/YYYY"
                                      value={chaser3Date}
                                      onChange={(e) => handleDateInput(e, setChaser3Date)}
                                      maxLength="10"
                                      disabled={!review.Chaser2IssuedDate || saving}
                                    />
                                    <button 
                                      className="btn btn-primary btn-sm" 
                                      type="button"
                                      onClick={() => handleSaveChaser(3, chaser3Date)}
                                      disabled={!review.Chaser2IssuedDate || saving || !chaser3Date}
                                    >
                                      Save
                                    </button>
                                  </div>
                                )}
                              </td>
                            </tr>
                            <tr>
                              <td>NTC</td>
                              <td>{review.NTCDueDate || '—'}</td>
                              <td>
                                {review.NTCIssuedDate ? (
                                  <input type="text" className="form-control form-control-sm" value={review.NTCIssuedDate} readOnly />
                                ) : (
                                  <div className="input-group input-group-sm">
                                    <input 
                                      type="text" 
                                      className="form-control form-control-sm" 
                                      placeholder="DD/MM/YYYY"
                                      value={ntcDate}
                                      onChange={(e) => handleDateInput(e, setNtcDate)}
                                      maxLength="10"
                                      disabled={!review.Chaser3IssuedDate || saving}
                                    />
                                    <button 
                                      className="btn btn-primary btn-sm" 
                                      type="button"
                                      onClick={handleSaveNTC}
                                      disabled={!review.Chaser3IssuedDate || saving || !ntcDate}
                                    >
                                      Save
                                    </button>
                                  </div>
                                )}
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      <div className="form-check mt-3">
                        <input 
                          type="checkbox" 
                          className="form-check-input" 
                          id="outreach_complete_chaser"
                          defaultChecked={review.outreach_complete}
                          onChange={handleOutreachCompleteChange}
                          disabled={saving || !canEditTasks}
                        />
                        <label className="form-check-label fw-semibold" htmlFor="outreach_complete_chaser">
                          Outreach Complete
                        </label>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Decision Section */}
            <div className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <div>
                  <h5 className="mb-0 d-inline">Decision</h5>
                  {status?.toLowerCase().includes('rework required') ? (
                    <span className="badge bg-warning ms-2">Rework Required</span>
                  ) : review.outcome && (
                    <span className="badge bg-success ms-2">Completed</span>
                  )}
                </div>
                <button 
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('decision')) {
                      newSections.delete('decision');
                    } else {
                      newSections.add('decision');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('decision') && (
                <div className="card-body">
                  {/* Show "Rework Required" status if task is in rework */}
                  {status?.toLowerCase().includes('rework required') && (
                    <div className="alert alert-warning mb-3">
                      <i className="bi bi-exclamation-triangle me-2"></i>
                      <strong>Rework Required</strong> - This task requires rework. Please review and update the necessary fields, then click "Rework Complete" when finished.
                    </div>
                  )}
                  
                  {/* Show "Completed" status if task is Awaiting QC or Completed (but not in rework) */}
                  {(status?.toLowerCase().includes('awaiting qc') || status?.toLowerCase().includes('completed')) && !status?.toLowerCase().includes('rework') && (
                    <div className="alert alert-success mb-3">
                      <i className="bi bi-check-circle me-2"></i>
                      <strong>Completed</strong> - This task has been reviewed and is {status?.toLowerCase().includes('awaiting qc') ? 'awaiting QC review' : 'completed'}.
                    </div>
                  )}
                  
                  {/* Outcome Dropdown */}
                  <div className="mb-3">
                    <label className="form-label">Outcome</label>
                    <select 
                      name="outcome"
                      className="form-select" 
                      value={selectedOutcome}
                      onChange={(e) => setSelectedOutcome(e.target.value)}
                      disabled={saving || isLocked()}
                    >
                      <option value="">Select…</option>
                      {data?.outcomes?.map((outcome, idx) => {
                        const optValue = typeof outcome === 'object' ? outcome.name : outcome;
                        return (
                          <option key={idx} value={optValue}>
                            {optValue}
                          </option>
                        );
                      })}
                    </select>
                  </div>

                  {/* Financial Crime Reason (conditional - only show if outcome contains "Financial Crime") */}
                  {selectedOutcome && selectedOutcome.toLowerCase().includes('financial crime') && (
                    <div className="mb-3">
                      <label className="form-label">Financial Crime Reason</label>
                      <select 
                        name="financial_crime_reason"
                        className="form-select" 
                        defaultValue={review.financial_crime_reason || review.fincrime_reason || ''}
                        disabled={saving || isLocked()}
                      >
                        <option value="">Select…</option>
                        <option value="Money Laundering">Money Laundering</option>
                        <option value="Tax Evasion">Tax Evasion</option>
                        <option value="Phoenixing">Phoenixing</option>
                      </select>
                    </div>
                  )}

                  {/* Decision Rationale */}
                  <div className="mb-3">
                    <label className="form-label">Rationale</label>
                    <textarea 
                      name="rationale"
                      className="form-control" 
                      rows="12"
                      style={{ minHeight: '200px', height: '200px' }}
                      defaultValue={review.rationale || ''}
                      disabled={saving || isLocked()}
                    />
                  </div>

                  {/* SME Query (for referring) - only show if AI SME is disabled AND user clicked "Refer for Technical Guidance" */}
                  {!isModuleEnabled('ai_sme') && showSmeQuery && (
                    <div className="mb-3">
                      <label className="form-label fw-semibold">SME Query</label>
                      <textarea 
                        name="sme_query"
                        className="form-control" 
                        rows="8"
                        placeholder="Enter your query for the SME..."
                        defaultValue={review.sme_query || ''}
                        disabled={saving || isLocked()}
                      />
                    </div>
                  )}

                  {/* Case Summary */}
                  <div className="mb-3">
                    <div className="d-flex justify-content-between align-items-center mb-1">
                      <label className="form-label mb-0">Case Summary</label>
                      <button 
                        type="button" 
                        className="btn btn-sm btn-outline-secondary" 
                        disabled={saving || isLocked()}
                        onClick={handleCreateCaseSummary}
                      >
                        <i className="bi bi-magic"></i> Create Case Summary
                      </button>
                    </div>
                    <textarea 
                      name="case_summary"
                      className="form-control" 
                      rows="12"
                      style={{ minHeight: '200px', height: '200px' }}
                      defaultValue={review.case_summary || ''}
                      disabled={saving || isLocked()}
                    />
                  </div>

                  {/* Action Buttons */}
                  <div className="action-bar mt-3 pt-3 border-top">
                    {saving && (
                      <div className="alert alert-info py-2 mb-2">
                        <small>Saving...</small>
                      </div>
                    )}
                    <div className="d-flex flex-wrap gap-2 justify-content-end">
                      {/* Show Rework Complete button if status is QC - Rework Required */}
                      {status?.toLowerCase().includes('rework required') && (
                        <button 
                          type="button"
                          className="btn btn-success"
                          onClick={handleReworkComplete}
                          disabled={saving || !canEditTasks}
                          title={!canEditTasks ? 'You do not have permission to edit tasks' : ''}
                        >
                          <i className="bi bi-check-circle"></i> Rework Complete
                        </button>
                      )}
                      
                      <button 
                        type="button"
                        className="btn btn-sm btn-primary" 
                        onClick={handleSaveProgress}
                        disabled={saving || isLocked() || !canEditTasks}
                        title={!canEditTasks ? 'You do not have permission to edit tasks' : ''}
                      >
                        <i className="bi bi-save"></i> Save Section
                      </button>
                      
                      {/* Only show Submit button if NOT in rework required status */}
                      {!status?.toLowerCase().includes('rework required') && (
                        <button 
                          type="button"
                          className="btn btn-success"
                          onClick={handleSubmit}
                          disabled={saving || isLocked() || !canEditTasks}
                          title={!canEditTasks ? 'You do not have permission to edit tasks' : ''}
                        >
                          <i className="bi bi-check2-circle"></i> Submit
                        </button>
                      )}
                      {/* Only show Refer to SME button if AI SME is disabled */}
                      {!isModuleEnabled('ai_sme') && (
                        <button 
                          type="button"
                          className="btn btn-warning"
                          onClick={handleReferSME}
                          disabled={saving || !canEditTasks}
                          title={!canEditTasks ? 'You do not have permission to edit tasks' : ''}
                        >
                          <i className="bi bi-person-gear"></i> Refer for Technical Guidance
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Identity Verification (Sumsub) */}
            {(identityVerification || review.sumsub_applicant_id) && (
              <div className="card shadow-sm mb-4">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">
                    <i className="fas fa-id-card me-2"></i>
                    Identity Verification
                  </h5>
                  <button 
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => {
                      const newSections = new Set(activeSections);
                      if (newSections.has('identity_verification')) {
                        newSections.delete('identity_verification');
                      } else {
                        newSections.add('identity_verification');
                      }
                      setActiveSections(newSections);
                    }}
                  >
                    {activeSections.has('identity_verification') ? 'Hide' : 'Show'}
                  </button>
                </div>
                {activeSections.has('identity_verification') && (
                  <div className="card-body">
                    {loadingIdentityVerification ? (
                      <div className="text-center py-3">
                        <div className="spinner-border spinner-border-sm text-primary" role="status">
                          <span className="visually-hidden">Loading...</span>
                        </div>
                      </div>
                    ) : (
                      <div>
                        {identityVerification ? (
                          <>
                            <div className="row mb-3">
                              <div className="col-md-6">
                                <strong>Applicant ID:</strong>
                                <p className="text-muted small mb-2">{review.sumsub_applicant_id || '—'}</p>
                              </div>
                              <div className="col-md-6">
                                <strong>Status:</strong>
                                <p className="mb-2">
                                  <span className={`badge ${
                                    identityVerification.reviewStatus === 'completed' || 
                                    identityVerification.reviewResult?.reviewAnswer === 'GREEN' 
                                      ? 'bg-success' 
                                      : identityVerification.reviewStatus === 'rejected' || 
                                        identityVerification.reviewResult?.reviewAnswer === 'RED'
                                        ? 'bg-danger'
                                        : 'bg-warning'
                                  }`}>
                                    {identityVerification.reviewStatus || identityVerification.review?.reviewStatus || 'Pending'}
                                  </span>
                                </p>
                              </div>
                            </div>
                            {identityVerification.reviewResult && (
                              <div className="mb-3">
                                <strong>Review Answer:</strong>
                                <p className="mb-2">
                                  <span className={`badge ${
                                    identityVerification.reviewResult.reviewAnswer === 'GREEN' 
                                      ? 'bg-success' 
                                      : identityVerification.reviewResult.reviewAnswer === 'RED'
                                        ? 'bg-danger'
                                        : identityVerification.reviewResult.reviewAnswer === 'YELLOW'
                                          ? 'bg-warning'
                                          : 'bg-secondary'
                                  }`}>
                                    {identityVerification.reviewResult.reviewAnswer || '—'}
                                  </span>
                                </p>
                              </div>
                            )}
                            {identityVerification.reviewDate && (
                              <div className="mb-3">
                                <strong>Review Date:</strong>
                                <p className="text-muted small mb-0">
                                  {new Date(identityVerification.reviewDate).toLocaleString()}
                                </p>
                              </div>
                            )}
                            {review.sumsub_verification_status && (
                              <div className="mb-3">
                                <strong>Verification Status:</strong>
                                <p className="text-muted small mb-0">{review.sumsub_verification_status}</p>
                              </div>
                            )}
                            {review.sumsub_verification_date && (
                              <div className="mb-3">
                                <strong>Verification Date:</strong>
                                <p className="text-muted small mb-0">
                                  {new Date(review.sumsub_verification_date).toLocaleString()}
                                </p>
                              </div>
                            )}
                          </>
                        ) : (
                          <div className="text-muted">
                            <p>No verification data available. Identity verification may not have been initiated yet.</p>
                            {review.sumsub_applicant_id && (
                              <button 
                                className="btn btn-sm btn-outline-primary"
                                onClick={fetchIdentityVerification}
                                disabled={loadingIdentityVerification}
                              >
                                <i className="bi bi-arrow-clockwise me-1"></i>
                                Refresh Status
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* AI SME Referrals - show if there are any AI SME referrals for this task */}
            {aiSmeReferrals.length > 0 && (
              <div className="card shadow-sm mb-4">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">
                    <i className="fas fa-brain me-2"></i>
                    AI SME Referrals ({aiSmeReferrals.length})
                  </h5>
                  <button 
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => {
                      const newSections = new Set(activeSections);
                      if (newSections.has('ai_sme')) {
                        newSections.delete('ai_sme');
                      } else {
                        newSections.add('ai_sme');
                      }
                      setActiveSections(newSections);
                    }}
                  >
                    {activeSections.has('ai_sme') ? 'Hide' : 'Show'}
                  </button>
                </div>
                {activeSections.has('ai_sme') && (
                  <div className="card-body">
                    {loadingAiReferrals ? (
                      <div className="text-center py-3">
                        <div className="spinner-border spinner-border-sm text-primary" role="status">
                          <span className="visually-hidden">Loading...</span>
                        </div>
                      </div>
                    ) : (
                      <div className="list-group list-group-flush">
                        {aiSmeReferrals.map((ref, idx) => (
                          <div key={ref.id || idx} className="list-group-item px-0">
                            <div className="d-flex justify-content-between align-items-start mb-2">
                              <div className="flex-grow-1">
                                <div className="d-flex align-items-center gap-2 mb-2">
                                  <span className={`badge ${ref.status === 'closed' ? 'bg-success' : 'bg-warning'}`}>
                                    {ref.status || 'open'}
                                  </span>
                                  <small className="text-muted">
                                    {ref.ts ? new Date(ref.ts).toLocaleString() : '—'}
                                  </small>
                                </div>
                                <h6 className="mb-1">Question:</h6>
                                <p className="mb-2 text-muted small">{ref.question || '—'}</p>
                                {ref.answer && (
                                  <>
                                    <h6 className="mb-1">Answer (Chatbot):</h6>
                                    <p className="mb-2 small text-muted">{ref.answer}</p>
                                  </>
                                )}
                                <h6 className="mb-1">SME Response:</h6>
                                <div className="mb-2">
                                  {ref.sme_response ? (
                                    <p className="mb-0 small fw-semibold">{ref.sme_response}</p>
                                  ) : (
                                    <p className="mb-0 text-muted small fst-italic">Awaiting SME response...</p>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="small text-muted">
                              {ref.count > 1 && `Asked ${ref.count} time${ref.count > 1 ? 's' : ''}`}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="mt-3">
                      <button 
                        className="btn btn-sm btn-outline-primary"
                        onClick={fetchAiSmeReferrals}
                        disabled={loadingAiReferrals}
                      >
                        <i className="bi bi-arrow-clockwise me-1"></i>
                        Refresh
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* SME Advice - only show if manual SME referral exists (not AI SME referrals) */}
            {/* Show only if there are no AI SME referrals for this task, meaning it's a manual referral */}
            {(review.sme_query || review.sme_response || review.referred_to_sme) && aiSmeReferrals.length === 0 && (
              <div className="card shadow-sm mb-4">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">SME Advice</h5>
                  <button 
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => {
                      const newSections = new Set(activeSections);
                      if (newSections.has('sme')) {
                        newSections.delete('sme');
                      } else {
                        newSections.add('sme');
                      }
                      setActiveSections(newSections);
                    }}
                  >
                    Toggle
                  </button>
                </div>
                {activeSections.has('sme') && (
                  <div className="card-body">
                    <div className="d-flex justify-content-between small mb-2">
                      <span className="text-muted">SME Reviewer</span>
                      <span className="fw-semibold">—</span>
                    </div>

                    <div className="mb-3">
                      <label className="form-label text-muted">Your SME Query</label>
                      <textarea className="form-control" rows="3" readOnly value={review.sme_query || '—'} />
                    </div>

                    <div className="mb-1">
                      <label className="form-label fw-semibold">Advice</label>
                      <textarea 
                        className="form-control" 
                        rows="6" 
                        readOnly 
                        value={review.sme_response || 'Awaiting SME response.'} 
                      />
                    </div>

                    <div className="small text-muted">
                      {review.sme_returned_date ? `Returned ${review.sme_returned_date}` : 
                       review.sme_selected_date ? `Referred ${review.sme_selected_date}` :
                       'SME not engaged yet.'}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* QC Assessment - only show if QC check was actually done */}
            {review.qc_check_date && (
              <div className="card shadow-sm mb-4">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">QC Assessment</h5>
                  <button 
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => {
                      const newSections = new Set(activeSections);
                      if (newSections.has('qc')) {
                        newSections.delete('qc');
                      } else {
                        newSections.add('qc');
                      }
                      setActiveSections(newSections);
                    }}
                  >
                    Toggle
                  </button>
                </div>
                {activeSections.has('qc') && (
                  <div className="card-body">
                    <div className="d-flex justify-content-between small mb-3">
                      <span className="text-muted">QC Reviewer</span>
                      <span className="fw-semibold">
                        {(() => {
                          const qcAssignedToId = review.qc_assigned_to;
                          if (!qcAssignedToId) return '—';
                          const qcUserName = data?.users?.[qcAssignedToId.toString()];
                          return qcUserName || review.qc_assigned_to_name || `User ${qcAssignedToId}`;
                        })()}
                      </span>
                    </div>

                    <div className="mb-3">
                      <label className="form-label">QC Outcome</label>
                      <input 
                        type="text" 
                        className="form-control form-control-sm" 
                        readOnly 
                        value={review.qc_outcome || '—'} 
                      />
                    </div>

                    <div className="mb-3">
                      <label className="form-label">QC Comment</label>
                      <textarea 
                        className="form-control form-control-sm" 
                        rows="4" 
                        readOnly 
                        value={review.qc_comment || '—'} 
                      />
                    </div>

                    {/* Only show "Rework Required" if rework is pending (not completed) */}
                    {review.qc_rework_required && 
                     review.qc_rework_required != 0 && 
                     review.qc_rework_required != '0' && 
                     (!review.qc_rework_completed || review.qc_rework_completed == 0 || review.qc_rework_completed == '0') ? (
                      <div className="alert alert-warning small mb-3">
                        <i className="bi bi-exclamation-triangle me-1"></i>
                        Rework Required
                      </div>
                    ) : null}

                    <div className="small text-muted">
                      Checked {new Date(review.qc_check_date).toLocaleString()}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="col-lg-3">
            {/* Empty for now - can add other sidebar widgets here */}
          </div>
        </div>
      </div>
    </>
  );
}

export default ReviewerPanel;


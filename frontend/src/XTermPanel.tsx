import React, { useEffect, useRef } from 'react';
import { Card, Text } from '@mantine/core';
import { Terminal } from 'xterm';
import 'xterm/css/xterm.css';

interface XTermPanelProps {
  timeline?: any[];
}

export default function XTermPanel({ timeline = [] }: XTermPanelProps) {
  const termRef = useRef<HTMLDivElement>(null);
  const xterm = useRef<Terminal|null>(null);
  const lastIndexRef = useRef(0);

  useEffect(() => {
    let term: Terminal | null = null;

    // Wait for layout to settle
    const timer = setTimeout(() => {
      if (!termRef.current) return;
      
      term = new Terminal({
        convertEol: true,
        fontSize: 13,
        theme: {
          background: '#181920',
        }
      });
      xterm.current = term;
      term.open(termRef.current);
      term.writeln('Welcome to the MCP Sec Terminal (pending real shell hook)...');
      
      // Print existing timeline events if any
      for (let i = 0; i < timeline.length; i++) {
        printEvent(term, timeline[i]);
      }
      lastIndexRef.current = timeline.length;
    }, 100);

    return () => {
      clearTimeout(timer);
      if (term) {
        const t = term;
        // Delay disposal to let any pending render animation frames or resize observers finish
        setTimeout(() => {
          try {
            t.dispose();
          } catch (e) {
            console.warn('Error disposing terminal:', e);
          }
        }, 100);
        xterm.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (xterm.current && timeline.length > lastIndexRef.current) {
      for (let i = lastIndexRef.current; i < timeline.length; i++) {
        printEvent(xterm.current, timeline[i]);
      }
      lastIndexRef.current = timeline.length;
    }
  }, [timeline]);

  function printEvent(term: Terminal, e: any) {
    if (!e || !e.type) return;
    const type = e.type;
    const task = e.task || {};
    try {
      if (type === 'task_requested') {
        term.writeln(`\r\x1b[36m[REQUESTED]\x1b[0m Requesting run of tool: \x1b[1m${task.tool_name}\x1b[0m`);
        if (task.command) {
          term.writeln(`            Command prepared: \x1b[90m${task.command}\x1b[0m`);
        }
      } else if (type === 'task_approved') {
        term.writeln(`\r\x1b[32m[APPROVED]\x1b[0m User approved the action.`);
      } else if (type === 'task_denied') {
        term.writeln(`\r\x1b[31m[DENIED]\x1b[0m User denied the action.`);
      } else if (type === 'task_running') {
        term.writeln(`\r\x1b[33m[RUNNING]\x1b[0m Spawning execution process...`);
        if (task.command) {
          term.writeln(`           Executing: \x1b[33m${task.command}\x1b[0m`);
        }
      } else if (type === 'task_completed') {
        term.writeln(`\r\x1b[32m[COMPLETED]\x1b[0m Process execution completed successfully.`);
        if (task.result) {
          term.writeln(`             Result: \x1b[32m${task.result}\x1b[0m`);
        }
      } else if (type === 'task_failed') {
        term.writeln(`\r\x1b[31m[FAILED]\x1b[0m Process execution failed.`);
        if (task.result) {
          term.writeln(`             Error: \x1b[31m${task.result}\x1b[0m`);
        }
      }
    } catch (err) {
      console.warn('Error writing to terminal:', err);
    }
  }

  return (
    <Card withBorder mt={20} p={6} radius={8} style={{backgroundColor:'#181920', color:'#eee',height:180}}>
      <Text size='xs' mb={4} style={{ color:'#f5f5f560' }}>Terminal (read-only demo)</Text>
      <div ref={termRef} style={{height:150, width:'100%',background:'#181920'}}/>
    </Card>
  );
}

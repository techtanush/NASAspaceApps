import {expect,it} from 'vitest';
import {render,screen} from '@testing-library/react';
import {Timestamp} from './index';

it('shows backend microseconds and offsets as bounded UTC seconds while retaining the exact source',()=>{
 const value='2026-11-12T23:59:59.123456-02:00';
 render(<Timestamp value={value}/>);
 const timestamp=screen.getByText('2026-11-13 01:59:59Z');
 expect(timestamp).toHaveAttribute('datetime',value);
 expect(timestamp).toHaveAttribute('title',value);
});

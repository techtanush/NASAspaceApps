import {test,expect} from '@playwright/test';
import {api} from './support/workbench';
test('declaring an optional rover value never invents a zero measurement',async({page})=>{
 await page.goto('/rovers');await expect(page.locator('main h1')).toHaveText('Rover library');
 await page.locator('[data-testid=input-rover-field][data-field=name]').fill('Explicit unknown rover');
 const value=page.locator('[data-testid=input-rover-field][data-field=max_route_m]');const availability=page.getByRole('group',{name:'Maximum route distance availability'});
 await expect(value).toBeDisabled();await availability.getByRole('button',{name:'Known',exact:true}).click();await expect(value).toBeEnabled();await expect(value).toHaveValue('');
 await page.getByTestId('btn-rover-save').click();await expect(page.getByText('Enter a declared value or select Unknown.',{exact:true}).first()).toBeVisible();
 await availability.getByRole('button',{name:'Unknown',exact:true}).click();await page.getByTestId('btn-rover-save').click();await expect(page.getByText('Saved revision 1',{exact:true})).toBeVisible();
 const rovers=await api<{items:{name:string;max_route_m:number|null}[]}>(page,'/rovers');expect(rovers.body.items.find(rover=>rover.name==='Explicit unknown rover')?.max_route_m).toBeNull();
});
